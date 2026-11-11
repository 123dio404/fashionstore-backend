"""Aislamiento multi-empresa (RNF de seguridad) en sincronización y conflictos."""

from __future__ import annotations

from sqlalchemy import select

from app.models.commerce import Sale, SalePayment
from app.models.inventory import Stock
from app.models.user import Role
from tests.conftest import post_sync, sale_operation


def test_sync_rejects_branch_from_another_tenant(client, db, seed):
    uuid = "99999999-1111-4111-8111-999999999999"

    response = post_sync(
        client,
        seed.cashier_a,
        [
            sale_operation(
                uuid=uuid,
                branch_id=seed.branch_b,  # Sucursal de la Empresa B
                stock_id=seed.stock_b,
                client_id=seed.client_a,
            )
        ],
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["conflicts"] == 1
    assert body["results"][0]["status"] == "CONFLICTO"

    db.expire_all()
    # El inventario de la otra empresa queda intacto.
    assert db.get(Stock, seed.stock_b).physical_stock == 5


def test_uuid_already_used_by_another_tenant_is_a_conflict(client, db, seed):
    uuid = "99999999-2222-4222-8222-999999999999"

    # La Empresa B sincroniza y registra la venta con ese UUID.
    first = post_sync(
        client,
        seed.admin_b,
        [
            sale_operation(
                uuid=uuid,
                branch_id=seed.branch_b,
                stock_id=seed.stock_b,
                client_id=seed.admin_b,
            )
        ],
    )
    assert first.status_code == 200, first.text
    assert first.json()["results"][0]["status"] == "CONFIRMADO"

    # La Empresa A intenta reutilizar el UUID: se rechaza sin tocar su inventario.
    second = post_sync(
        client,
        seed.cashier_a,
        [
            sale_operation(
                uuid=uuid,
                branch_id=seed.branch_a,
                stock_id=seed.stock_a,
                client_id=seed.client_a,
            )
        ],
    )

    assert second.status_code == 200, second.text
    body = second.json()
    assert body["conflicts"] == 1
    assert body["results"][0]["status"] == "CONFLICTO"
    assert "otra empresa" in body["results"][0]["message"].lower()

    db.expire_all()
    assert db.get(Stock, seed.stock_a).physical_stock == 1
    assert db.get(Stock, seed.stock_b).physical_stock == 4


def test_tenant_cannot_resolve_another_tenants_conflict(client, db, seed):
    uuid = "99999999-3333-4333-8333-999999999999"

    # Se genera un conflicto real en la Empresa B (stock ya consumido).
    consume = post_sync(
        client,
        seed.admin_b,
        [
            sale_operation(
                uuid="99999999-4444-4444-8444-999999999999",
                branch_id=seed.branch_b,
                stock_id=seed.stock_b,
                client_id=seed.admin_b,
            )
        ],
    )
    assert consume.json()["results"][0]["status"] == "CONFIRMADO"

    # Vaciamos el stock de B y provocamos el conflicto.
    db.expire_all()
    stock_b = db.get(Stock, seed.stock_b)
    stock_b.physical_stock = 0
    db.commit()

    conflict_response = post_sync(
        client,
        seed.admin_b,
        [
            sale_operation(
                uuid=uuid,
                branch_id=seed.branch_b,
                stock_id=seed.stock_b,
                client_id=seed.admin_b,
            )
        ],
    )
    assert conflict_response.json()["results"][0]["status"] == "CONFLICTO"

    db.expire_all()
    conflict = db.scalar(select(Sale).where(Sale.offline_uuid == uuid))
    assert conflict is not None
    assert conflict.sync_status == "CONFLICTO"

    # El administrador de A no puede resolver un conflicto de B.
    response = client.post(
        f"/api/v1/sync/conflicts/{conflict.id}/resolve",
        params={"action": "compensar"},
        headers=seed.token(seed.admin_a),
    )

    assert response.status_code == 403
    db.expire_all()
    still = db.get(Sale, conflict.id)
    assert still.sync_status == "CONFLICTO"
    payment = db.scalar(select(SalePayment).where(SalePayment.sale_id == conflict.id))
    assert payment.status == "pendiente"


def test_roles_are_seeded_for_tenant_scope(db, seed):
    """Sanity check del fixture: cada usuario pertenece a su empresa."""
    from app.models.user import User

    admin_a = db.get(User, seed.admin_a)
    admin_b = db.get(User, seed.admin_b)
    assert admin_a.role == Role.ADMINISTRADOR
    assert admin_a.tenant_id == seed.tenant_a
    assert admin_b.tenant_id == seed.tenant_b
