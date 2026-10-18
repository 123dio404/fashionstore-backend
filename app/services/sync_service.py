from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.commerce import Sale, SaleItem, SalePayment, Reservation, ReservationItem
from app.models.finance import PaymentStatus
from app.models.inventory import Stock, InventoryMovement, MovementType
from app.models.user import User
from app.schemas.sync import (
    SyncBatchRequest,
    SyncBatchResponse,
    SyncOperationResult,
)


def process_sync_batch(
    db: Session,
    user: User,
    data: SyncBatchRequest,
) -> SyncBatchResponse:
    """
    Procesa un lote de operaciones registradas offline (PWA o Móvil) garantizando:
    1. Idempotencia absoluta (RNF05) usando el UUID de cliente.
    2. Integridad transaccional y descuento atómico de inventario.
    3. Detección y registro explícito de CONFLICTOS si el stock central es insuficiente (RN-05).
    """
    confirmed = 0
    conflicts = 0
    results: list[SyncOperationResult] = []

    tenant_id = user.tenant_id

    for op in data.operations:
        op_type = op.type.upper().strip()

        if op_type == "SALE":
            # 1. Comprobar Idempotencia (RNF05)
            existing_sale = db.scalar(select(Sale).where(Sale.offline_uuid == op.uuid))
            if existing_sale:
                results.append(
                    SyncOperationResult(
                        uuid=op.uuid,
                        type=op_type,
                        status="DUPLICADO_IDEMPOTENTE",
                        server_id=existing_sale.id,
                        message="Operación previamente procesada y confirmada.",
                    )
                )
                continue

            # 2. Validar disponibilidad de Stock central
            has_stock_conflict = False
            conflict_reason = ""
            for item in op.items:
                stock = db.get(Stock, item.stock_id)
                if not stock or stock.physical_stock < item.quantity:
                    has_stock_conflict = True
                    curr = stock.physical_stock if stock else 0
                    conflict_reason = f"Stock central insuficiente para inventario #{item.stock_id} (Disponible: {curr}, Requerido: {item.quantity})"
                    break

            if has_stock_conflict:
                # 3. Registrar Venta en estado CONFLICTO para auditoría sin restar inventario
                conflict_sale = Sale(
                    client_id=op.client_id or user.id,
                    user_id=user.id,
                    branch_id=op.branch_id,
                    tenant_id=tenant_id,
                    sale_date=op.created_at,
                    total=op.total,
                    sale_type="Venta Offline (Contado)",
                    offline_uuid=op.uuid,
                    sync_status="CONFLICTO",
                    items=[
                        SaleItem(
                            stock_id=i.stock_id,
                            quantity=i.quantity,
                            unit_price=i.unit_price,
                        )
                        for i in op.items
                    ],
                )
                db.add(conflict_sale)
                db.commit()
                db.refresh(conflict_sale)

                conflicts += 1
                results.append(
                    SyncOperationResult(
                        uuid=op.uuid,
                        type=op_type,
                        status="CONFLICTO",
                        server_id=conflict_sale.id,
                        message=conflict_reason,
                    )
                )
            else:
                # 4. Descontar Stock y Confirmar Venta
                sale_items: list[SaleItem] = []
                for i in op.items:
                    stock = db.get(Stock, i.stock_id)
                    stock.physical_stock -= i.quantity
                    db.add(
                        InventoryMovement(
                            movement_type=MovementType.VENTA,
                            inventory_id=stock.id,
                            quantity=-i.quantity,
                            reason=f"Venta offline confirmada (UUID: {op.uuid[:8]})",
                        )
                    )
                    sale_items.append(
                        SaleItem(
                            stock_id=i.stock_id,
                            quantity=i.quantity,
                            unit_price=i.unit_price,
                        )
                    )

                confirmed_sale = Sale(
                    client_id=op.client_id or user.id,
                    user_id=user.id,
                    branch_id=op.branch_id,
                    tenant_id=tenant_id,
                    sale_date=op.created_at,
                    total=op.total,
                    sale_type="Venta Offline (Contado)",
                    offline_uuid=op.uuid,
                    sync_status="CONFIRMADO",
                    items=sale_items,
                    payments=[
                        SalePayment(
                            amount=op.total,
                            status=PaymentStatus.COMPLETADO.value,
                            paid_at=op.created_at,
                            reference=f"OFFLINE-{op.uuid[:8]}",
                        )
                    ],
                )
                db.add(confirmed_sale)
                db.commit()
                db.refresh(confirmed_sale)

                confirmed += 1
                results.append(
                    SyncOperationResult(
                        uuid=op.uuid,
                        type=op_type,
                        status="CONFIRMADO",
                        server_id=confirmed_sale.id,
                        message="Venta sincronizada e inventario central actualizado.",
                    )
                )

        elif op_type == "RESERVATION":
            # Idempotencia de Reservas
            existing_res = db.scalar(select(Reservation).where(Reservation.offline_uuid == op.uuid))
            if existing_res:
                results.append(
                    SyncOperationResult(
                        uuid=op.uuid,
                        type=op_type,
                        status="DUPLICADO_IDEMPOTENTE",
                        server_id=existing_res.id,
                        message="Reserva ya registrada previamente.",
                    )
                )
                continue

            # Crear reserva
            new_res = Reservation(
                client_id=op.client_id or user.id,
                branch_id=op.branch_id,
                tenant_id=tenant_id,
                reservation_date=op.created_at.date(),
                reservation_time=op.created_at.time(),
                status="Pendiente",
                offline_uuid=op.uuid,
                sync_status="CONFIRMADO",
                items=[
                    ReservationItem(stock_id=i.stock_id, quantity=i.quantity)
                    for i in op.items
                ],
            )
            # Reservar stock si existe
            for i in op.items:
                stock = db.get(Stock, i.stock_id)
                if stock:
                    stock.reserved_stock += i.quantity

            db.add(new_res)
            db.commit()
            db.refresh(new_res)

            confirmed += 1
            results.append(
                SyncOperationResult(
                    uuid=op.uuid,
                    type=op_type,
                    status="CONFIRMADO",
                    server_id=new_res.id,
                    message="Reserva offline registrada exitosamente.",
                )
            )

    return SyncBatchResponse(
        processed=len(data.operations),
        confirmed=confirmed,
        conflicts=conflicts,
        results=results,
    )
