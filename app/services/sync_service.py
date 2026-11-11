from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.models.commerce import Sale, SaleItem, SalePayment, Reservation, ReservationItem
from app.models.finance import PaymentStatus
from app.models.inventory import Stock, InventoryMovement, MovementType
from app.models.user import User
from app.schemas.sync import (
    SyncBatchRequest,
    SyncBatchResponse,
    SyncOperationResult,
)

# RN-03: sin conexión solo se cobra en efectivo. Las pasarelas (Stripe/QR) y el
# datáfono requieren red, por lo que no pueden confirmar un cobro offline.
CASH_PAYMENT_METHODS = {"efectivo", "cash", "contado"}

# Estrategia de resolución de conflictos (RN-05):
#  - "compensar"/"reembolsar"/"anular": reembolso total y anulación de la venta.
#  - "reasignar"/"confirmar": se vuelve a intentar el descuento atómico de stock
#    y, si hay disponibilidad, la venta queda confirmada.
COMPENSATION_ACTIONS = {"compensar", "compensar_administrativo", "reembolsar", "anular"}
REASSIGN_ACTIONS = {"reasignar", "confirmar", "confirmar_venta"}


def _stock_available(db: Session, stock_id: int) -> int:
    """Disponibilidad real leída de la base (sin caché de identidad)."""
    row = db.execute(
        select(Stock.physical_stock, Stock.reserved_stock).where(Stock.id == stock_id)
    ).first()
    if row is None:
        return 0
    return max(0, int(row[0]) - int(row[1]))


def _decrement_stock_atomic(
    db: Session,
    *,
    stock_id: int,
    branch_id: int,
    tenant_id: int | None,
    quantity: int,
) -> tuple[bool, str]:
    """Descuenta stock con una operación atómica condicional.

    `UPDATE inventario SET stock_actual = stock_actual - qty
      WHERE id = :id AND id_sucursal = :branch AND stock_actual - stock_reservado >= qty`

    PostgreSQL bloquea la fila durante el UPDATE. Si dos dispositivos sincronizan
    la última unidad al mismo tiempo, solo uno obtiene `rowcount == 1`; el otro
    debe registrarse como CONFLICTO. Esto elimina la sobreventa que existía al
    leer y restar en memoria.
    """
    stock = db.get(Stock, stock_id)
    if stock is None:
        return False, f"El inventario #{stock_id} no existe."
    if stock.branch_id != branch_id:
        return False, (
            f"El inventario #{stock_id} pertenece a otra sucursal "
            f"(#{stock.branch_id}, se intentó vender en #{branch_id})."
        )
    if tenant_id is not None:
        branch = db.get(Branch, stock.branch_id)
        if branch is None or branch.tenant_id != tenant_id:
            return False, "El inventario no pertenece a la empresa de la sesión."

    result = db.execute(
        update(Stock)
        .where(
            Stock.id == stock_id,
            Stock.branch_id == branch_id,
            (Stock.physical_stock - Stock.reserved_stock) >= quantity,
        )
        .values(
            physical_stock=Stock.physical_stock - quantity,
            updated_at=func.now(),
        )
    )
    if result.rowcount != 1:
        available = _stock_available(db, stock_id)
        return False, (
            f"Stock central insuficiente para inventario #{stock_id} "
            f"(Disponible: {available}, Requerido: {quantity})."
        )
    return True, ""


def _conflict_sale(
    db: Session,
    *,
    op,
    user: User,
    tenant_id: int | None,
    reason: str,
) -> Sale:
    """Registra la venta offline en CONFLICTO sin tocar el inventario central."""
    sale = Sale(
        client_id=op.client_id or user.id,
        user_id=user.id,
        branch_id=op.branch_id,
        tenant_id=tenant_id,
        sale_date=op.created_at,
        total=op.total,
        sale_type="Venta Offline (Contado)",
        offline_uuid=op.uuid,
        sync_status="CONFLICTO",
        delivery_status="PENDIENTE",
        customer_notes=reason[:255],
        items=[
            SaleItem(
                stock_id=i.stock_id,
                quantity=i.quantity,
                unit_price=i.unit_price,
            )
            for i in op.items
        ],
        payments=[
            SalePayment(
                amount=op.total,
                status=PaymentStatus.PENDIENTE.value,
                paid_at=None,
                reference=f"OFFLINE-CONFLICTO-{op.uuid[:8]}",
            )
        ],
    )
    db.add(sale)
    db.commit()
    db.refresh(sale)
    return sale


def process_sync_batch(
    db: Session,
    user: User,
    data: SyncBatchRequest,
) -> SyncBatchResponse:
    """
    Procesa un lote de operaciones registradas offline (PWA o Móvil) garantizando:
    1. Idempotencia absoluta (RNF05) usando el UUID de cliente.
    2. Integridad transaccional y descuento atómico de inventario (RN-05).
    3. Detección y registro explícito de CONFLICTOS si el stock central es insuficiente.
    4. Solo ventas en efectivo sin conexión (RN-03).
    """
    confirmed = 0
    conflicts = 0
    results: list[SyncOperationResult] = []

    tenant_id = user.tenant_id

    for op in data.operations:
        op_type = op.type.upper().strip()

        if op_type == "SALE":
            # 1. Idempotencia (RNF05). El UUID es único incluso entre tenants.
            existing_sale = db.scalar(select(Sale).where(Sale.offline_uuid == op.uuid))
            if existing_sale:
                if tenant_id is not None and existing_sale.tenant_id != tenant_id:
                    results.append(
                        SyncOperationResult(
                            uuid=op.uuid,
                            type=op_type,
                            status="CONFLICTO",
                            message="El UUID ya fue utilizado por otra empresa.",
                        )
                    )
                    conflicts += 1
                    continue
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

            # 2. RN-03: sin conexión solo se puede cobrar en efectivo.
            payment_method = (op.payment_method or "efectivo").strip().lower()
            if payment_method not in CASH_PAYMENT_METHODS:
                conflict_sale = _conflict_sale(
                    db,
                    op=op,
                    user=user,
                    tenant_id=tenant_id,
                    reason=(
                        "Venta offline rechazada: solo se permite efectivo sin conexión "
                        f"(RN-03). Método recibido: {op.payment_method}."
                    ),
                )
                conflicts += 1
                results.append(
                    SyncOperationResult(
                        uuid=op.uuid,
                        type=op_type,
                        status="CONFLICTO",
                        server_id=conflict_sale.id,
                        message=(
                            "Solo se permiten ventas en efectivo sin conexión (RN-03). "
                            "Cobra con tarjeta/QR únicamente cuando haya red."
                        ),
                    )
                )
                continue

            # 3. Validación de sucursal/tenant antes de tocar stock.
            branch = db.get(Branch, op.branch_id)
            if branch is None or (tenant_id is not None and branch.tenant_id != tenant_id):
                conflict_sale = _conflict_sale(
                    db,
                    op=op,
                    user=user,
                    tenant_id=tenant_id,
                    reason="La sucursal no existe o no pertenece a la empresa de la sesión.",
                )
                conflicts += 1
                results.append(
                    SyncOperationResult(
                        uuid=op.uuid,
                        type=op_type,
                        status="CONFLICTO",
                        server_id=conflict_sale.id,
                        message="Sucursal inválida para la empresa autenticada.",
                    )
                )
                continue
            if not branch.is_active:
                conflict_sale = _conflict_sale(
                    db,
                    op=op,
                    user=user,
                    tenant_id=tenant_id,
                    reason="La sucursal está inactiva y no puede recibir ventas.",
                )
                conflicts += 1
                results.append(
                    SyncOperationResult(
                        uuid=op.uuid,
                        type=op_type,
                        status="CONFLICTO",
                        server_id=conflict_sale.id,
                        message="Sucursal inactiva: no se registró la venta.",
                    )
                )
                continue

            # 4. Descuento atómico de TODAS las líneas. Si una falla, se revierte
            # el lote completo y la venta se registra como CONFLICTO.
            failure: str | None = None
            for item in op.items:
                ok, reason = _decrement_stock_atomic(
                    db,
                    stock_id=item.stock_id,
                    branch_id=op.branch_id,
                    tenant_id=tenant_id,
                    quantity=item.quantity,
                )
                if not ok:
                    failure = reason
                    break

            if failure is not None:
                db.rollback()
                # Releer la venta por si otro proceso insertó el mismo UUID
                # mientras se intentaba descontar stock.
                raced = db.scalar(select(Sale).where(Sale.offline_uuid == op.uuid))
                if raced is not None:
                    results.append(
                        SyncOperationResult(
                            uuid=op.uuid,
                            type=op_type,
                            status="DUPLICADO_IDEMPOTENTE",
                            server_id=raced.id,
                            message="Operación previamente procesada y confirmada.",
                        )
                    )
                    continue

                conflict_sale = _conflict_sale(
                    db,
                    op=op,
                    user=user,
                    tenant_id=tenant_id,
                    reason=failure,
                )
                conflicts += 1
                results.append(
                    SyncOperationResult(
                        uuid=op.uuid,
                        type=op_type,
                        status="CONFLICTO",
                        server_id=conflict_sale.id,
                        message=failure,
                    )
                )
                continue

            # 5. Stock descontado de forma atómica: registrar venta y movimientos.
            sale_items: list[SaleItem] = []
            for item in op.items:
                db.add(
                    InventoryMovement(
                        movement_type=MovementType.VENTA,
                        inventory_id=item.stock_id,
                        quantity=-item.quantity,
                        reason=f"Venta offline confirmada (UUID: {op.uuid[:8]})",
                    )
                )
                sale_items.append(
                    SaleItem(
                        stock_id=item.stock_id,
                        quantity=item.quantity,
                        unit_price=item.unit_price,
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
                delivery_status="PAGADO",
                items=sale_items,
                payments=[
                    SalePayment(
                        amount=op.total,
                        status=PaymentStatus.COMPLETADO.value,
                        paid_at=op.created_at,
                        reference=f"OFFLINE-CASH-{op.uuid[:8]}",
                    )
                ],
            )
            db.add(confirmed_sale)
            try:
                db.commit()
                db.refresh(confirmed_sale)
            except IntegrityError:
                # Dos peticiones simultáneas con el mismo UUID: una gana y la
                # otra se reporta como duplicada idempotente.
                db.rollback()
                raced = db.scalar(select(Sale).where(Sale.offline_uuid == op.uuid))
                if raced is not None:
                    results.append(
                        SyncOperationResult(
                            uuid=op.uuid,
                            type=op_type,
                            status="DUPLICADO_IDEMPOTENTE",
                            server_id=raced.id,
                            message="Operación previamente procesada y confirmada.",
                        )
                    )
                    continue
                raise

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

            branch = db.get(Branch, op.branch_id)
            if branch is None or (tenant_id is not None and branch.tenant_id != tenant_id):
                results.append(
                    SyncOperationResult(
                        uuid=op.uuid,
                        type=op_type,
                        status="CONFLICTO",
                        message="Sucursal inválida para la empresa autenticada.",
                    )
                )
                conflicts += 1
                continue

            # Reservar stock de forma atómica para no exceder la disponibilidad.
            failed_reason: str | None = None
            for item in op.items:
                result = db.execute(
                    update(Stock)
                    .where(
                        Stock.id == item.stock_id,
                        Stock.branch_id == op.branch_id,
                        (Stock.physical_stock - Stock.reserved_stock) >= item.quantity,
                    )
                    .values(
                        reserved_stock=Stock.reserved_stock + item.quantity,
                        updated_at=func.now(),
                    )
                )
                if result.rowcount != 1:
                    failed_reason = (
                        f"Stock insuficiente para reservar inventario #{item.stock_id} "
                        f"(Requerido: {item.quantity})."
                    )
                    break

            if failed_reason is not None:
                db.rollback()
                results.append(
                    SyncOperationResult(
                        uuid=op.uuid,
                        type=op_type,
                        status="CONFLICTO",
                        message=failed_reason,
                    )
                )
                conflicts += 1
                continue

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


def _apply_compensation(db: Session, sale: Sale, note: str) -> None:
    """Anula la venta conflictiva y deja el pago listo para reembolso."""
    uuid8 = (sale.offline_uuid or str(sale.id))[:8]
    for payment in sale.payments:
        payment.status = PaymentStatus.REEMBOLSADO.value
        payment.reference = f"REEMBOLSO-{uuid8}"
    sale.sync_status = "RESUELTO_ADMIN"
    sale.delivery_status = "ANULADO"
    sale.customer_notes = note[:255]


def _apply_reassignment(db: Session, sale: Sale, note: str) -> None:
    """Vuelve a intentar el descuento atómico y confirma la venta si hay stock."""
    for item in sale.items:
        ok, reason = _decrement_stock_atomic(
            db,
            stock_id=item.stock_id,
            branch_id=sale.branch_id,
            tenant_id=sale.tenant_id,
            quantity=item.quantity,
        )
        if not ok:
            db.rollback()
            raise HTTPException(status_code=409, detail=reason)
        db.add(
            InventoryMovement(
                movement_type=MovementType.VENTA,
                inventory_id=item.stock_id,
                quantity=-item.quantity,
                reason=f"Conflicto offline reasignado (UUID: {(sale.offline_uuid or str(sale.id))[:8]})",
            )
        )
    for payment in sale.payments:
        payment.status = PaymentStatus.COMPLETADO.value
        payment.paid_at = payment.paid_at or datetime.now(timezone.utc)
    sale.sync_status = "RESUELTO_ADMIN"
    sale.delivery_status = "PAGADO"
    sale.customer_notes = note[:255]


def resolve_conflict(
    db: Session,
    sale: Sale,
    *,
    action: str,
    user: User,
    note: str | None = None,
) -> Sale:
    """Resuelve un conflicto con compensación real y notificación al cliente.

    Regla de prioridad (RN-05): la primera operación que logra el descuento
    atómico del stock al sincronizar conserva la unidad. La segunda queda en
    CONFLICTO y el administrador decide entre:
      * reembolsar/compensar (por defecto), o
      * reasignar stock si apareció disponibilidad.
    """
    if sale.sync_status != "CONFLICTO":
        raise HTTPException(
            status_code=409,
            detail=f"La venta #{sale.id} no está en conflicto (estado actual: {sale.sync_status}).",
        )

    normalized = (action or "compensar").strip().lower()
    if normalized not in COMPENSATION_ACTIONS | REASSIGN_ACTIONS:
        raise HTTPException(
            status_code=422,
            detail=(
                "Acción inválida. Use 'compensar' (reembolso) o 'reasignar' "
                "(confirmar si hay stock)."
            ),
        )

    default_note = (
        "Conflicto de stock resuelto con reembolso al cliente."
        if normalized in COMPENSATION_ACTIONS
        else "Conflicto de stock resuelto reasignando la última unidad."
    )
    resolution_note = note or default_note
    refunded = normalized in COMPENSATION_ACTIONS

    if refunded:
        _apply_compensation(db, sale, resolution_note)
    else:
        _apply_reassignment(db, sale, resolution_note)

    db.commit()
    db.refresh(sale)

    # Auditoría + notificación al cliente afectado, al cajero y al administrador.
    try:
        from app.services.notification_service import notify_offline_conflict_resolved

        branch = db.get(Branch, sale.branch_id)
        client = db.get(User, sale.client_id) if sale.client_id else None
        cashier = db.get(User, sale.user_id) if sale.user_id else None
        notify_offline_conflict_resolved(
            db,
            sale,
            branch,
            client,
            cashier,
            resolution=normalized,
            refunded=refunded,
            note=note,
        )
        db.commit()
    except Exception:
        db.rollback()

    return sale
