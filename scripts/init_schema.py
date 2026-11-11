"""Inicializa y actualiza el esquema de la base al desplegar.

Crea todas las tablas desde los modelos SQLAlchemy (la misma fuente que usa el
desarrollo), sincroniza las columnas/índices/llaves foráneas nuevas en tablas
que ya existían y marca la cadena de migraciones de Alembic como aplicada para
que las migraciones futuras corran por encima de él.

Motivo: la cadena histórica de Alembic mezcla tablas en inglés (`reservations`,
`products`) con tablas en español (`reserva`, `producto`) y no corre de cero
sobre una base limpia; los modelos son el esquema real del sistema.

Además, `Base.metadata.create_all` solo crea tablas que faltan: no agrega
columnas a tablas existentes. Sin este paso, una base ya creada se queda sin
las columnas nuevas (p. ej. `categoria.id_empresa`) y los endpoints fallan con
`UndefinedColumn`.
"""
import app.models  # noqa: F401  (registra todas las tablas en Base.metadata)
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.schema import AddConstraint, CreateColumn
from app.core.database import Base, engine


def _quote(identifier: str) -> str:
    return engine.dialect.identifier_preparer.quote(identifier)


def _sync_columns() -> None:
    """Agrega a las tablas existentes las columnas nuevas declaradas en los modelos."""
    inspector = inspect(engine)
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing = {column["name"] for column in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing:
                continue
            ddl = str(CreateColumn(column).compile(dialect=engine.dialect))
            try:
                with engine.begin() as conn:
                    conn.execute(
                        text(f"ALTER TABLE {_quote(table.name)} ADD COLUMN {ddl}")
                    )
                print(f"==> Columna agregada: {table.name}.{column.name}")
            except Exception as exc:  # noqa: BLE001 - el arranque no debe caerse
                print(
                    f"==> ADVERTENCIA: no se pudo agregar "
                    f"{table.name}.{column.name}: {exc}"
                )


def _sync_foreign_keys() -> None:
    """Agrega las llaves foráneas declaradas en los modelos que falten en la base."""
    inspector = inspect(engine)
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing = {
            tuple(fk["constrained_columns"])
            for fk in inspector.get_foreign_keys(table.name)
        }
        for constraint in table.foreign_key_constraints:
            columns = tuple(column.name for column in constraint.columns)
            if not columns or columns in existing:
                continue
            try:
                with engine.begin() as conn:
                    conn.execute(AddConstraint(constraint))
                print(f"==> Llave foránea agregada: {table.name}{columns}")
            except Exception as exc:  # noqa: BLE001 - el arranque no debe caerse
                print(
                    f"==> ADVERTENCIA: no se pudo agregar la llave foránea "
                    f"{table.name}{columns}: {exc}"
                )


# Restricciones UNIQUE que los modelos ya no declaran. Al pasar a multitenant,
# `categoria.nombre` dejó de ser único global (cada empresa puede tener las
# mismas categorías), pero la base conserva la restricción original.
_STALE_UNIQUE_COLUMNS: dict[str, set[str]] = {
    "categoria": {"nombre"},
}


def _drop_stale_unique_constraints() -> None:
    """Elimina restricciones UNIQUE que el modelo ya no declara."""
    inspector = inspect(engine)
    for table_name, stale_columns in _STALE_UNIQUE_COLUMNS.items():
        if not inspector.has_table(table_name):
            continue
        for constraint in inspector.get_unique_constraints(table_name):
            if set(constraint.get("column_names") or []) != stale_columns:
                continue
            name = constraint.get("name")
            if not name:
                continue
            try:
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            f"ALTER TABLE {_quote(table_name)} "
                            f"DROP CONSTRAINT {_quote(name)}"
                        )
                    )
                print(f"==> Restricción UNIQUE obsoleta eliminada: {table_name}.{name}")
            except Exception as exc:  # noqa: BLE001 - el arranque no debe caerse
                print(
                    f"==> ADVERTENCIA: no se pudo eliminar la restricción UNIQUE "
                    f"{table_name}.{name}: {exc}"
                )


def _sync_indexes() -> None:
    """Crea los índices declarados en los modelos que falten en la base."""
    inspector = inspect(engine)
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing = {index["name"] for index in inspector.get_indexes(table.name)}
        for index in table.indexes:
            if not index.name or index.name in existing:
                continue
            try:
                index.create(bind=engine, checkfirst=True)
                print(f"==> Índice agregado: {index.name}")
            except Exception as exc:  # noqa: BLE001 - el arranque no debe caerse
                print(
                    f"==> ADVERTENCIA: no se pudo crear el índice "
                    f"{index.name}: {exc}"
                )


def main() -> None:
    print("==> Creando esquema desde los modelos (create_all)")
    Base.metadata.create_all(bind=engine)
    print("==> Sincronizando columnas nuevas en tablas existentes")
    _sync_columns()
    print("==> Sincronizando llaves foráneas nuevas")
    _sync_foreign_keys()
    print("==> Eliminando restricciones UNIQUE obsoletas")
    _drop_stale_unique_constraints()
    print("==> Sincronizando índices nuevos")
    _sync_indexes()
    print("==> Marcando migraciones como aplicadas (alembic stamp head)")
    command.stamp(Config("alembic.ini"), "head")
    print("==> Esquema listo")


if __name__ == "__main__":
    main()
