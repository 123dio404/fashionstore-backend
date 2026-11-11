"""Punto 4 · RF CU-10 / CU-12: venta offline en efectivo, de punta a punta.

Evidencia automatizada de:
  * RN-03: sin conexión solo se permite efectivo.
  * RNF05: idempotencia por UUID del cliente.
  * Descuento de inventario central al sincronizar.
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.models.commerce import Sale, SalePayment
from app.models.inventory import InventoryMovement, MovementType, Stock
from app.models.user import Role, User
from tests.conftest import post_sync, sale_operation


def test_offline_cash_sale_confirms_and_decrements_stock(client, db, seed):
    uuid = "11111111-1111-4111-8111-111111111111"

    response = post_sync(
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

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["processed"] == 1
    assert body["confirmed"] == 1
    assert body["conflicts"] == 0
    assert body["results"][0]["status"] == "CONFIRMADO"

    db.expire_all()
    stock = db.get(Stock, seed.stock_a)
    assert stock is not None
    assert stock.physical_stock == 0  # 1 unidad inicial - 1 vendida

    sale = db.scalar(select(Sale).where(Sale.offline_uuid == uuid))
    assert sale is not None
    assert sale.sync_status == "CONFIRMADO"
    assert sale.sale_type == "Venta Offline (Contado)"
    assert sale.tenant_id == seed.tenant_a
    assert sale.branch_id == seed.branch_a
    assert sale.client_id == seed.client_a
    assert sale.user_id == seed.cashier_a

    payment = db.scalar(select(SalePayment).where(SalePayment.sale_id == sale.id))
    assert payment is not None
    assert payment.status == "completado"
    assert payment.reference is not None
    assert payment.reference.startswith("OFFLINE-CASH-")

    movement = db.scalar(
        select(InventoryMovement).where(
            InventoryMovement.inventory_id == seed.stock_a,
            InventoryMovement.movement_type == MovementType.VENTA,
        )
    )
    assert movement is not None
    assert movement.quantity == -1


def test_same_uuid_is_idempotent_and_does_not_sell_twice(client, db, seed):
    uuid = "22222222-2222-4222-8222-222222222222"
    operation = sale_operation(
        uuid=uuid,
        branch_id=seed.branch_a,
        stock_id=seed.stock_a,
        client_id=seed.client_a,
    )

    first = post_sync(client, seed.cashier_a, [operation])
    second = post_sync(client, seed.cashier_a, [operation])

    assert first.status_code == 200, first.text
    assert first.json()["results"][0]["status"] == "CONFIRMADO"
    assert second.status_code == 200, second.text
    assert second.json()["confirmed"] == 0
    assert second.json()["results"][0]["status"] == "DUPLICADO_IDEMPOTENTE"

    db.expire_all()
    sales = db.scalar(
        select(func.count(Sale.id)).where(Sale.offline_uuid == uuid)
    )
    assert sales == 1
    assert db.get(Stock, seed.stock_a).physical_stock == 0


def test_non_cash_offline_sale_is_rejected_as_conflict(client, db, seed):
    uuid = "33333333-3333-4333-8333-333333333333"

    response = post_sync(
        client,
        seed.cashier_a,
        [
            sale_operation(
                uuid=uuid,
                branch_id=seed.branch_a,
                stock_id=seed.stock_a,
                payment_method="tarjeta",
                client_id=seed.client_a,
            )
        ],
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["confirmed"] == 0
    assert body["conflicts"] == 1
    assert body["results"][0]["status"] == "CONFLICTO"
    assert "efectivo" in body["results"][0]["message"].lower()

    db.expire_all()
    # El stock no se toca: la venta con tarjeta offline nunca se cobró.
    assert db.get(Stock, seed.stock_a).physical_stock == 1
    sale = db.scalar(select(Sale).where(Sale.offline_uuid == uuid))
    assert sale is not None
    assert sale.sync_status == "CONFLICTO"
    payment = db.scalar(select(SalePayment).where(SalePayment.sale_id == sale.id))
    assert payment is not None
    assert payment.status == "pendiente"


def test_inactive_branch_cannot_receive_offline_sales(client, db, seed):
    uuid = "44444444-4444-4444-8444-444444444444"

    response = post_sync(
        client,
        seed.cashier_a,
        [
            sale_operation(
                uuid=uuid,
                branch_id=seed.branch_a_inactive,
                stock_id=seed.stock_a,
                client_id=seed.client_a,
            )
        ],
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["conflicts"] == 1
    assert body["results"][0]["status"] == "CONFLICTO"
    assert "inactiva" in body["results"][0]["message"].lower()

    db.expire_all()
    assert db.get(Stock, seed.stock_a).physical_stock == 1


def test_client_can_sync_own_offline_sale(client, db, seed):
    """El rol Cliente puede sincronizar sus compras hechas sin conexión."""
    uuid = "55555555-5555-4555-8555-555555555555"

    response = post_sync(
        client,
        seed.client_a,
        [
            sale_operation(
                uuid=uuid,
                branch_id=seed.branch_a,
                stock_id=seed.stock_a,
                client_id=seed.client_a,
            )
        ],
    )

    assert response.status_code == 200, response.text
    assert response.json()["results"][0]["status"] == "CONFIRMADO"
    db.expire_all()
    sale = db.scalar(select(Sale).where(Sale.offline_uuid == uuid))
    assert sale is not None
    assert sale.user_id == seed.client_a
    cliente = db.get(User, seed.client_a)
    assert cliente is not None
    assert cliente.role == Role.CLIENTE
