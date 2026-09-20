"""Inicializa el esquema de la base al desplegar.

Crea todas las tablas desde los modelos SQLAlchemy (la misma fuente que usa el
desarrollo) y marca la cadena de migraciones de Alembic como aplicada para que
las migraciones futuras corran por encima de él.

Motivo: la cadena histórica de Alembic mezcla tablas en inglés (`reservations`,
`products`) con tablas en español (`reserva`, `producto`) y no corre de cero
sobre una base limpia; los modelos son el esquema real del sistema.
"""
import app.models  # noqa: F401  (registra todas las tablas en Base.metadata)
from alembic import command
from alembic.config import Config
from app.core.database import Base, engine


def main() -> None:
    print("==> Creando esquema desde los modelos (create_all)")
    Base.metadata.create_all(bind=engine)
    print("==> Marcando migraciones como aplicadas (alembic stamp head)")
    command.stamp(Config("alembic.ini"), "head")
    print("==> Esquema listo")


if __name__ == "__main__":
    main()