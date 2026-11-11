"""Punto 5 · RN-05: dos dispositivos vendiendo la última unidad.

Evidencia automatizada de:
  * Descuento atómico y condicional del stock (solo una operación gana).
  * Registro de la operación perdedora como CONFLICTO, sin sobreventa.
  * Resolución administrativa con compensación (reembolso) o reasignación.
  * Notificación al cliente afectado, al cajero y al administrador.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models.commerce import Sale, SalePayment
from app.models.inventory import InventoryMovement, MovementType, Stock
from app.models.notification import Notification
from app.models.user import User
from app.schemas.sync import SyncBatchRequest
from app.services.sync_service import process_sync_batch
from tests.conftest import post_sync, sale_operation


def _conflict_sale(db, uuid: str) -> Sale:
    sale = db.scalar(select(Sale).where(Sale.offline_uuid == uuid))
    assert sale is not None
    return sale


def test_second_device_gets_conflict_and_first_keeps_the_unit(client, db, seed):
    uuid_device_1 = "aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa"
    uuid_device_2 = "bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb"

    first = post_sync(
        client,
        seed.cashier_a,
        [
            sale_operation(
                uuid=uuid_device_1,
                branch_id=seed.branch_a,
                stock_id=seed.stock_a,
                client_id=seed.client_a,
            )
        ],
    )
    second = post_sync(
        client,
        seed.cashier_a,
        [
            sale_operation(
                uuid=uuid_device_2,
                branch_id=seed.branch_a,
                stock_id=seed.stock_a,
                client_id=seed.client_a,
            )
        ],
    )

    assert first.status_code == 200, first.text
    assert first.json()["results"][0]["status"] == "CONFIRMADO"
    assert second.status_code == 200, second.text
    assert second.json()["confirmed"] == 0
    assert second.json()["conflicts"] == 1
    assert second.json()["results"][0]["status"] == "CONFLICTO"

    db.expire_all()
    stock = db.get(Stock, seed.stock_a)
    assert stock.physical_stock == 0  # Nunca baja de cero: no hay sobreventa.

    winner = _conflict_sale(db, uuid_device_1)
    loser = _conflict_sale(db, uuid_device_2)
    assert winner.sync_status == "CONFIRMADO"
    assert loser.sync_status == "CONFLICTO"
    assert winner.id != loser.id

    winner_payment = db.scalar(select(SalePayment).where(SalePayment.sale_id == winner.id))
    loser_payment = db.scalar(select(SalePayment).where(SalePayment.sale_id == loser.id))
    assert winner_payment.status == "completado"
    assert loser_payment.status == "pendiente"


def test_concurrent_sync_of_last_unit_has_exactly_one_winner(db, seed):
    """Dos hilos sincronizan la última unidad al mismo tiempo.

    La prueba es de nivel de servicio (sesiones independientes) para ejercitar
    el `UPDATE ... WHERE stock_actual - stock_reservado >= cantidad` real.
    """

    def run(uuid: str):
        session = SessionLocal()
        try:
            user = session.get(User, seed.cashier_a)
            request = SyncBatchRequest.model_validate(
                {
                    "operations": [
                        sale_operation(
                            uuid=uuid,
                            branch_id=seed.branch_a,
                            stock_id=seed.stock_a,
                            client_id=seed.client_a,
                        )
                    ]
                }
            )
            result = process_sync_batch(session, user, request)
            return result.results[0].status
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(
            pool.map(
                run,
                [
                    "cccccccc-3333-4333-8333-cccccccccccc",
                    "dddddddd-4444-4444-8444-dddddddddddd",
                ],
            )
        )

    assert sorted(statuses) == ["CONFIRMADO", "CONFLICTO"]

    db.expire_all()
    assert db.get(Stock, seed.stock_a).physical_stock == 0
    assert db.scalar(select(func.count(Sale.id))) == 2
    assert (
        db.scalar(select(func.count(Sale.id)).where(Sale.sync_status == "CONFIRMADO"))
        == 1
    )
    assert (
        db.scalar(select(func.count(Sale.id)).where(Sale.sync_status == "CONFLICTO"))
        == 1
    )


def test_resolve_conflict_with_compensation_refunds_and_notifies(client, db, seed):
    won_uuid = "eeeeeeee-5555-4555-8555-eeeeeeeeeeee"
    lost_uuid = "ffffffff-6666-4666-8666-ffffffffffff"

    post_sync(
        client,
        seed.cashier_a,
        [
            sale_operation(
                uuid=won_uuid,
                branch_id=seed.branch_a,
                stock_id=seed.stock_a,
                client_id=seed.client_a,
            )
        ],
    )
    post_sync(
        client,
        seed.cashier_a,
        [
            sale_operation(
                uuid=lost_uuid,
                branch_id=seed.branch_a,
                stock_id=seed.stock_a,
                client_id=seed.client_a,
            )
        ],
    )

    db.expire_all()
    conflict = _conflict_sale(db, lost_uuid)
    assert conflict.sync_status == "CONFLICTO"
    conflict_id = conflict.id

    response = client.post(
        f"/api/v1/sync/conflicts/{conflict_id}/resolve",
        params={"action": "compensar", "note": "Sin stock: se reembolsa en caja."},
        headers=seed.token(seed.admin_a),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["sync_status"] == "RESUELTO_ADMIN"
    assert body["delivery_status"] == "ANULADO"

    db.expire_all()
    resolved = db.get(Sale, conflict_id)
    assert resolved.sync_status == "RESUELTO_ADMIN"
    assert resolved.delivery_status == "ANULADO"
    payment = db.scalar(select(SalePayment).where(SalePayment.sale_id == conflict_id))
    assert payment.status == "reembolsado"
    assert payment.reference.startswith("REEMBOLSO-")
    # El stock sigue en cero: la primera venta conservó la unidad.
    assert db.get(Stock, seed.stock_a).physical_stock == 0

    # El cliente afectado recibe la notificación del reembolso.
    client_notif = db.scalar(
        select(Notification).where(
            Notification.user_id == seed.client_a,
            Notification.title.contains("Reembolso"),
        )
    )
    assert client_notif is not None
    assert "reembolso" in client_notif.message.lower()

    # El administrador recibe la auditoría de la compensación.
    admin_notif = db.scalar(
        select(Notification).where(
            Notification.target_role == "Administrador",
            Notification.title.contains("compensado"),
        )
    )
    assert admin_notif is not None


def test_resolve_conflict_with_reassignment_confirms_when_stock_returns(client, db, seed):
    won_uuid = "12121212-7777-4777-8777-121212121212"
    lost_uuid = "34343434-8888-4888-8888-343434343434"

    post_sync(
        client,
        seed.cashier_a,
        [
            sale_operation(
                uuid=won_uuid,
                branch_id=seed.branch_a,
                stock_id=seed.stock_a,
                client_id=seed.client_a,
            )
        ],
    )
    post_sync(
        client,
        seed.cashier_a,
        [
            sale_operation(
                uuid=lost_uuid,
                branch_id=seed.branch_a,
                stock_id=seed.stock_a,
                client_id=seed.client_a,
            )
        ],
    )

    db.expire_all()
    conflict = _conflict_sale(db, lost_uuid)
    conflict_id = conflict.id

    # Llega reposición: ahora sí hay una unidad disponible para reasignar.
    stock = db.get(Stock, seed.stock_a)
    stock.physical_stock = 1
    db.commit()

    response = client.post(
        f"/api/v1/sync/conflicts/{conflict_id}/resolve",
        params={"action": "reasignar"},
        headers=seed.token(seed.admin_a),
    )

    assert response.status_code == 200, response.text
    assert response.json()["sync_status"] == "RESUELTO_ADMIN"
    assert response.json()["delivery_status"] == "PAGADO"

    db.expire_all()
    assert db.get(Stock, seed.stock_a).physical_stock == 0
    payment = db.scalar(select(SalePayment).where(SalePayment.sale_id == conflict_id))
    assert payment.status == "completado"
    movement = db.scalar(
        select(InventoryMovement).where(
            InventoryMovement.inventory_id == seed.stock_a,
            InventoryMovement.quantity == -1,
            InventoryMovement.reason.contains("reasignado"),
        )
    )
    assert movement is not None
    assert movement.movement_type == MovementType.VENTA


def test_cannot_resolve_a_sale_that_is_not_in_conflict(client, db, seed):
    uuid = "56565656-9999-4999-8999-565656565656"
    post_sync(
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
    db.expire_all()
    sale = _conflict_sale(db, uuid)
    assert sale.sync_status == "CONFIRMADO"

    response = client.post(
        f"/api/v1/sync/conflicts/{sale.id}/resolve",
        params={"action": "compensar"},
        headers=seed.token(seed.admin_a),
    )

    assert response.status_code == 409
    assert "no está en conflicto" in response.json()["detail"]
