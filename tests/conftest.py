"""Fixtures de la suite de pruebas críticas (punto 7 · RF/RNF).

Cubre:
  * RF CU-10 / CU-12: venta en efectivo offline y sincronización idempotente.
  * RN-05: dos dispositivos que venden la última unidad (conflicto de stock).
  * RNF05: idempotencia por UUID de cliente.
  * Aislamiento multi-empresa (tenant) en sincronización y resolución.
  * RNF11: gating del plan SaaS para reportes con IA.

La suite usa PostgreSQL real porque `app/core/database.py` lo exige. Por defecto
apunta a `localhost:5433/fashionstore_test`; se puede sobreescribir con
`DATABASE_URL`. Cada prueba recrea el esquema para partir de un estado limpio.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal

# Las variables deben definirse ANTES de importar `app`, porque la configuración
# y el engine se construyen a nivel de módulo.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg2://fashionstore:fashionstore@localhost:5433/fashionstore_test",
)
os.environ["ENVIRONMENT"] = "test"
os.environ["SEED_DEMO_USERS"] = "false"
os.environ["SEED_DEMO_CATALOG"] = "false"
os.environ["SEED_DEMO_PURCHASES"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import app.models  # noqa: E402,F401  (registra todas las tablas en Base.metadata)
from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.models.branch import Branch, City  # noqa: E402
from app.models.inventory import Stock  # noqa: E402
from app.models.product import Category, Product, ProductVariant  # noqa: E402
from app.models.tenant import Plan, Subscription, Tenant  # noqa: E402
from app.models.user import Role, Rol, User, UsuarioRol  # noqa: E402
from main import app as fastapi_app  # noqa: E402


@dataclass
class Seed:
    """Identificadores sembrados que consumen las pruebas."""

    tenant_a: int
    tenant_b: int
    branch_a: int
    branch_b: int
    branch_a_inactive: int
    stock_a: int
    stock_b: int
    product_a: int
    variant_a: int
    admin_a: int
    cashier_a: int
    client_a: int
    admin_b: int

    def token(self, user_id: int) -> dict[str, str]:
        return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def _role(db: Session, role: Role) -> Rol:
    rol = db.scalar(select(Rol).where(Rol.nombre == role.value))
    if rol is None:
        rol = Rol(nombre=role.value)
        db.add(rol)
        db.flush()
    return rol


def _user(db: Session, *, tenant: Tenant | None, role: Role, email: str, name: str) -> User:
    user = User(
        tenant_id=tenant.id if tenant else None,
        full_name=name,
        email=email,
        password_hash="not-used-in-tests",
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(UsuarioRol(id_usuario=user.id, id_rol=_role(db, role).id))
    db.flush()
    return user


@pytest.fixture(scope="session", autouse=True)
def _database_available() -> None:
    """Falla temprano con un mensaje claro si PostgreSQL de pruebas no responde."""
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
    except Exception as exc:  # pragma: no cover - depende del entorno
        pytest.skip(f"PostgreSQL de pruebas no disponible: {exc}")


@pytest.fixture()
def db(seed: Seed) -> Session:
    """Sesión directa para verificar el estado persistido tras una petición."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def seed() -> Seed:
    """Recrea el esquema y siembra dos empresas con catálogo y stock."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    try:
        # ── Planes SaaS ─────────────────────────────────────────────────────
        basic = Plan(
            name="Básico",
            max_branches=2,
            has_ai_reports=False,
            monthly_price=Decimal("29.99"),
            is_active=True,
        )
        enterprise = Plan(
            name="Empresarial",
            max_branches=15,
            has_ai_reports=True,
            monthly_price=Decimal("129.99"),
            is_active=True,
        )
        session.add_all([basic, enterprise])
        session.flush()

        # ── Empresas y suscripciones ────────────────────────────────────────
        tenant_a = Tenant(name="Empresa A", slug="empresa-a", status="Activo")
        tenant_b = Tenant(name="Empresa B", slug="empresa-b", status="Activo")
        session.add_all([tenant_a, tenant_b])
        session.flush()
        session.add_all(
            [
                Subscription(
                    tenant_id=tenant_a.id,
                    plan_id=basic.id,
                    status="Activa",
                ),
                Subscription(
                    tenant_id=tenant_b.id,
                    plan_id=enterprise.id,
                    status="Activa",
                ),
            ]
        )

        city = City(name="Ciudad Test")
        session.add(city)
        session.flush()

        branch_a = Branch(
            tenant_id=tenant_a.id,
            city_id=city.id,
            name="Sucursal A",
            address="Calle A #1",
            phone="70000001",
            is_active=True,
        )
        branch_a_inactive = Branch(
            tenant_id=tenant_a.id,
            city_id=city.id,
            name="Sucursal A Inactiva",
            address="Calle A #2",
            phone="70000002",
            is_active=False,
        )
        branch_b = Branch(
            tenant_id=tenant_b.id,
            city_id=city.id,
            name="Sucursal B",
            address="Calle B #1",
            phone="70000003",
            is_active=True,
        )
        session.add_all([branch_a, branch_a_inactive, branch_b])
        session.flush()

        # ── Catálogo ────────────────────────────────────────────────────────
        category = Category(tenant_id=tenant_a.id, name="Camisas")
        session.add(category)
        session.flush()

        product_a = Product(
            tenant_id=tenant_a.id,
            category_id=category.id,
            name="Camisa Test",
            brand="Marca Test",
            price=Decimal("100.00"),
            is_active=True,
        )
        session.add(product_a)
        session.flush()

        variant_a = ProductVariant(
            product_id=product_a.id,
            codigo="TEST-001",
            price=Decimal("100.00"),
            is_active=True,
        )
        session.add(variant_a)
        session.flush()

        # Stock inicial de 1 unidad para poder reproducir "última unidad".
        stock_a = Stock(
            branch_id=branch_a.id,
            variant_id=variant_a.id,
            physical_stock=1,
            min_stock=0,
            reserved_stock=0,
        )
        stock_b = Stock(
            branch_id=branch_b.id,
            variant_id=variant_a.id,
            physical_stock=5,
            min_stock=0,
            reserved_stock=0,
        )
        session.add_all([stock_a, stock_b])
        session.flush()

        # ── Usuarios ────────────────────────────────────────────────────────
        admin_a = _user(
            session,
            tenant=tenant_a,
            role=Role.ADMINISTRADOR,
            email="admin.a@test.com",
            name="Admin A",
        )
        cashier_a = _user(
            session,
            tenant=tenant_a,
            role=Role.CAJERO,
            email="cajero.a@test.com",
            name="Cajero A",
        )
        client_a = _user(
            session,
            tenant=tenant_a,
            role=Role.CLIENTE,
            email="cliente.a@test.com",
            name="Cliente A",
        )
        admin_b = _user(
            session,
            tenant=tenant_b,
            role=Role.ADMINISTRADOR,
            email="admin.b@test.com",
            name="Admin B",
        )

        session.commit()

        ids = Seed(
            tenant_a=tenant_a.id,
            tenant_b=tenant_b.id,
            branch_a=branch_a.id,
            branch_b=branch_b.id,
            branch_a_inactive=branch_a_inactive.id,
            stock_a=stock_a.id,
            stock_b=stock_b.id,
            product_a=product_a.id,
            variant_a=variant_a.id,
            admin_a=admin_a.id,
            cashier_a=cashier_a.id,
            client_a=client_a.id,
            admin_b=admin_b.id,
        )
        return ids
    finally:
        session.close()


@pytest.fixture()
def client() -> TestClient:
    with TestClient(fastapi_app) as test_client:
        yield test_client


def sale_operation(
    *,
    uuid: str,
    branch_id: int,
    stock_id: int,
    quantity: int = 1,
    total: str = "100.00",
    payment_method: str = "efectivo",
    client_id: int | None = None,
) -> dict:
    """Operación con el contrato real de `POST /api/v1/sync/batch`."""
    return {
        "uuid": uuid,
        "type": "SALE",
        "created_at": "2026-11-10T10:00:00Z",
        "branch_id": branch_id,
        "client_id": client_id,
        "total": total,
        "payment_method": payment_method,
        "items": [
            {
                "stock_id": stock_id,
                "quantity": quantity,
                "unit_price": "100.00",
            }
        ],
    }


def post_sync(client: TestClient, user_id: int, operations: list[dict]):
    return client.post(
        "/api/v1/sync/batch",
        json={"operations": operations},
        headers={"Authorization": f"Bearer {create_access_token(user_id)}"},
    )
