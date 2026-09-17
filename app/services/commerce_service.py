from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.models.commerce import (
    Cart,
    CartItem,
    Reservation,
    ReservationItem,
    Sale,
    SaleItem,
    SalePayment,
)
from app.models.inventory import InventoryMovement, MovementType, Stock
from app.models.user import Role, User
from app.schemas.commerce import (
    CartItemRequest,
    CartItemResponse,
    CartResponse,
    CheckoutRequest,
    PosSaleCreate,
    ReservationCreate,
    ReservationUpdate,
    PaymentStatus,
    ReceiptResponse,
)


class MockPaymentProvider:
    """Deterministic provider used by the API until a real gateway is configured."""

    def charge(self, amount: Decimal, status: PaymentStatus, reference: str | None = None) -> dict:
        return {
            "status": status.value,
            "reference": reference,
            "paid_at": datetime.now(timezone.utc) if status == PaymentStatus.COMPLETADO else None,
        }


PAYMENT_PROVIDERS = {"mock": MockPaymentProvider()}


def _stock(db: Session, stock_id: int) -> Stock:
    stock = db.get(Stock, stock_id)
    if stock is None:
        raise HTTPException(404, "Stock record not found")
    return stock


def get_or_create_cart(db: Session, user_id: int) -> Cart:
    cart = db.scalar(
        select(Cart)
        .where(Cart.user_id == user_id, Cart.status == "activo")
        .order_by(Cart.created_at.desc())
        .limit(1)
    )
    if cart is None:
        cart = Cart(user_id=user_id, status="activo")
        db.add(cart)
        db.commit()
        db.refresh(cart)
    return cart


def get_cart(db: Session, user_id: int) -> CartResponse:
    cart = get_or_create_cart(db, user_id)
    items: list[CartItemResponse] = []
    total = Decimal("0")
    for ci in cart.items:
        variant = ci.stock.variant
        product = variant.product
        total += ci.price * ci.quantity
        items.append(
            CartItemResponse(
                id=ci.id,
                stock_id=ci.stock_id,
                quantity=ci.quantity,
                price=ci.price,
                variant_id=variant.id,
                product_id=product.id,
                product_name=product.name,
                size=variant.size.name if variant.size else None,
                color=variant.color.name if variant.color else None,
            )
        )
    return CartResponse(id=cart.id, status=cart.status, items=items, total=total)


def add_to_cart(db: Session, user_id: int, data: CartItemRequest) -> CartResponse:
    stock = _stock(db, data.stock_id)
    available = stock.physical_stock - stock.reserved_stock
    if available <= 0:
        raise HTTPException(409, "Stock not available")
    cart = get_or_create_cart(db, user_id)
    existing = next((i for i in cart.items if i.stock_id == data.stock_id), None)
    quantity = data.quantity + (existing.quantity if existing else 0)
    if quantity > available:
        raise HTTPException(409, "Requested quantity exceeds available stock")
    if existing:
        existing.quantity = quantity
    else:
        cart.items.append(
            CartItem(stock_id=data.stock_id, quantity=data.quantity, price=stock.variant.product.price)
        )
    db.commit()
    return get_cart(db, user_id)


def update_cart_item(db: Session, user_id: int, item_id: int, quantity: int) -> CartResponse:
    cart = get_or_create_cart(db, user_id)
    item = next((i for i in cart.items if i.id == item_id), None)
    if item is None:
        raise HTTPException(404, "Cart item not found")
    if quantity > (item.stock.physical_stock - item.stock.reserved_stock):
        raise HTTPException(409, "Requested quantity exceeds available stock")
    item.quantity = quantity
    db.commit()
    return get_cart(db, user_id)


def remove_cart_item(db: Session, user_id: int, item_id: int) -> CartResponse:
    cart = get_or_create_cart(db, user_id)
    item = next((i for i in cart.items if i.id == item_id), None)
    if item is None:
        raise HTTPException(404, "Cart item not found")
    db.delete(item)
    db.commit()
    return get_cart(db, user_id)


def checkout(db: Session, user_id: int, data: CheckoutRequest) -> Sale:
    if db.get(Branch, data.branch_id) is None:
        raise HTTPException(404, "Branch not found")
    cart = get_or_create_cart(db, user_id)
    if not cart.items:
        raise HTTPException(400, "Cart is empty")
    total = Decimal("0")
    for ci in cart.items:
        if ci.quantity > (ci.stock.physical_stock - ci.stock.reserved_stock):
            raise HTTPException(409, f"Insufficient stock for {ci.stock_id}")
        total += ci.price * ci.quantity
    provider = PAYMENT_PROVIDERS.get(data.payment_provider)
    if provider is None:
        raise HTTPException(400, f"Unsupported payment provider: {data.payment_provider}")
    payment = provider.charge(total, data.payment_status, data.payment_reference)
    sale = Sale(client_id=user_id, user_id=user_id, branch_id=data.branch_id, total=total, sale_type="digital")
    sale.payments.append(
        SalePayment(amount=total, status=payment["status"], paid_at=payment["paid_at"],
                    reference=payment["reference"] or f"ORD-{user_id}-{datetime.now().timestamp():.0f}")
    )
    if data.payment_status != PaymentStatus.COMPLETADO:
        db.add(sale)
        db.commit()
        db.refresh(sale)
        return sale
    for ci in cart.items:
        ci.stock.physical_stock -= ci.quantity
        sale.items.append(SaleItem(stock_id=ci.stock_id, quantity=ci.quantity, unit_price=ci.price))
        db.add(
            InventoryMovement(
                movement_type=MovementType.VENTA,
                inventory_id=ci.stock.id,
                quantity=-ci.quantity,
                reason="Venta digital",
            )
        )
    db.add(sale)
    db.flush()
    if sale.payments[0].reference is None:
        sale.payments[0].reference = f"ORD-{sale.id:012d}"
    cart.status = "completado"
    db.commit()
    db.refresh(sale)
    return sale


def get_sale(db: Session, sale_id: int) -> Sale:
    sale = db.get(Sale, sale_id)
    if sale is None:
        raise HTTPException(404, "Sale not found")
    return sale


def list_sales(db: Session, client_id: int | None = None) -> list[Sale]:
    q = select(Sale).order_by(Sale.sale_date.desc(), Sale.id)
    if client_id is not None:
        q = q.where(Sale.client_id == client_id)
    return list(db.scalars(q).all())


def pos_sale(db: Session, user_id: int, data: PosSaleCreate) -> Sale:
    if db.get(Branch, data.branch_id) is None:
        raise HTTPException(404, "Branch not found")
    client = db.get(User, data.client_id)
    if client is None:
        raise HTTPException(404, "Client not found")
    if client.role != Role.CLIENTE:
        raise HTTPException(422, "POS sales require a client user")
    total = Decimal("0")
    entries = []
    for inp in data.items:
        stock = _stock(db, inp.stock_id)
        if stock.branch_id != data.branch_id:
            raise HTTPException(422, f"Stock {inp.stock_id} does not belong to the sale branch")
        if inp.quantity > (stock.physical_stock - stock.reserved_stock):
            raise HTTPException(409, f"Insufficient available stock for {inp.stock_id}")
        unit_price = stock.variant.product.price
        total += unit_price * inp.quantity
        entries.append((stock, inp.quantity, unit_price))
    if total <= 0:
        raise HTTPException(400, "Sale total must be positive")
    provider = PAYMENT_PROVIDERS.get(data.payment_provider)
    if provider is None:
        raise HTTPException(400, f"Unsupported payment provider: {data.payment_provider}")
    requested_status = data.payment_status or (
        PaymentStatus.COMPLETADO if data.paid else PaymentStatus.PENDIENTE
    )
    payment = provider.charge(total, requested_status, data.payment_reference)
    sale = Sale(client_id=data.client_id, user_id=user_id, branch_id=data.branch_id, total=total, sale_type="pos")
    sale.payments.append(SalePayment(amount=total, status=payment["status"],
                                     paid_at=payment["paid_at"], reference=payment["reference"]))
    if requested_status != PaymentStatus.COMPLETADO:
        db.add(sale)
        db.commit()
        db.refresh(sale)
        return sale
    for stock, quantity, unit_price in entries:
        stock.physical_stock -= quantity
        sale.items.append(SaleItem(stock_id=stock.id, quantity=quantity, unit_price=unit_price))
        db.add(
            InventoryMovement(
                movement_type=MovementType.VENTA,
                inventory_id=stock.id,
                quantity=-quantity,
                reason="Venta POS",
            )
        )
    db.add(sale)
    db.flush()
    if sale.payments[0].reference is None:
        sale.payments[0].reference = f"POS-{sale.id:012d}"
    db.commit()
    db.refresh(sale)
    return sale


def create_reservation(db: Session, user_id: int, data: ReservationCreate) -> Reservation:
    if db.get(Branch, data.branch_id) is None:
        raise HTTPException(404, "Branch not found")
    entries = []
    requested: dict[int, int] = {}
    for inp in data.items:
        stock = _stock(db, inp.stock_id)
        if stock.branch_id != data.branch_id:
            raise HTTPException(422, f"Stock {inp.stock_id} does not belong to the reservation branch")
        requested[inp.stock_id] = requested.get(inp.stock_id, 0) + inp.quantity
        if requested[inp.stock_id] > (stock.physical_stock - stock.reserved_stock):
            raise HTTPException(409, f"Insufficient available stock for {inp.stock_id}")
        overlapping = db.scalar(
            select(ReservationItem.id)
            .join(Reservation)
            .where(
                Reservation.branch_id == data.branch_id,
                Reservation.reservation_date == data.reservation_date,
                Reservation.reservation_time == data.reservation_time,
                ReservationItem.stock_id == inp.stock_id,
                Reservation.status.in_(("pendiente", "confirmada", "preparacion", "lista", "asignada", "en_probador", "en_tienda", "checkout")),
            ).limit(1)
        )
        if overlapping is not None:
            raise HTTPException(409, "Stock already reserved for this branch and time")
    entries = [(_stock(db, stock_id), quantity) for stock_id, quantity in requested.items()]
    reservation = Reservation(
        client_id=user_id,
        branch_id=data.branch_id,
        reservation_date=data.reservation_date,
        reservation_time=data.reservation_time,
        status="pendiente",
    )
    for stock, quantity in entries:
        stock.reserved_stock += quantity
        reservation.items.append(ReservationItem(stock_id=stock.id, quantity=quantity))
        db.add(
            InventoryMovement(
                movement_type=MovementType.RESERVA,
                inventory_id=stock.id,
                quantity=quantity,
                reason="Reserva probador",
            )
        )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    return reservation


def get_reservation(db: Session, reservation_id: int) -> Reservation:
    reservation = db.get(Reservation, reservation_id)
    if reservation is None:
        raise HTTPException(404, "Reservation not found")
    return reservation


def list_reservations(
    db: Session,
    client_id: int | None = None,
    status: str | None = None,
    branch_id: int | None = None,
    reservation_date=None,
) -> list[Reservation]:
    q = select(Reservation).order_by(Reservation.reservation_date.desc(), Reservation.reservation_time)
    if client_id is not None:
        q = q.where(Reservation.client_id == client_id)
    if status is not None:
        q = q.where(Reservation.status == status)
    if branch_id is not None:
        q = q.where(Reservation.branch_id == branch_id)
    if reservation_date is not None:
        q = q.where(Reservation.reservation_date == reservation_date)
    return list(db.scalars(q).all())


def _release_reserved(db: Session, reservation: Reservation) -> None:
    for item in reservation.items:
        stock = db.get(Stock, item.stock_id)
        if stock is not None and stock.reserved_stock >= item.quantity:
            stock.reserved_stock -= item.quantity
            db.add(
                InventoryMovement(
                    movement_type=MovementType.RESERVA,
                    inventory_id=stock.id,
                    quantity=-item.quantity,
                    reason="Liberación reserva",
                )
            )


def _consume_reserved(db: Session, reservation: Reservation) -> None:
    for item in reservation.items:
        stock = db.get(Stock, item.stock_id)
        if stock is None or stock.physical_stock < item.quantity:
            raise HTTPException(409, f"Insufficient stock for reservation item {item.stock_id}")
        stock.physical_stock -= item.quantity
        db.add(
            InventoryMovement(
                movement_type=MovementType.VENTA,
                inventory_id=stock.id,
                quantity=-item.quantity,
                reason="Consumo reserva probador",
            )
        )


def _restore_consumed(db: Session, reservation: Reservation) -> None:
    for item in reservation.items:
        stock = db.get(Stock, item.stock_id)
        if stock is not None:
            stock.physical_stock += item.quantity
            db.add(
                InventoryMovement(
                    movement_type=MovementType.AJUSTE,
                    inventory_id=stock.id,
                    quantity=item.quantity,
                    reason="Devolución reserva probador",
                )
            )


def update_reservation(db: Session, reservation_id: int, data: ReservationUpdate) -> Reservation:
    reservation = get_reservation(db, reservation_id)
    values = data.model_dump(exclude_unset=True)
    new_status = values.pop("status", None)
    now = datetime.now(timezone.utc)
    if new_status is not None:
        transitions = {
            "pendiente": {"confirmada", "preparacion", "cancelada"},
            "confirmada": {"preparacion", "cancelada"},
            "preparacion": {"lista", "cancelada"},
            "lista": {"asignada", "cancelada"},
            "asignada": {"en_probador", "cancelada"},
            "en_probador": {"checkout", "cancelada"},
            "checkout": {"completada", "reembolsada", "devuelta"},
            "completada": {"devuelta", "reembolsada"},
        }
        if new_status != reservation.status and new_status not in transitions.get(reservation.status, set()):
            raise HTTPException(409, f"Invalid reservation transition: {reservation.status} -> {new_status}")
        if new_status == "preparacion":
            reservation.prepared_at = now
        elif new_status == "asignada":
            if reservation.fitting_room is None:
                raise HTTPException(422, "A fitting room is required")
            reservation.assigned_at = now
        elif new_status == "checkout":
            reservation.checked_out_at = now
        elif new_status in ("reembolsada", "devuelta"):
            reservation.refunded_at = now
    for k, v in values.items():
        setattr(reservation, k, v)
    if new_status is not None and new_status != reservation.status:
        old_status = reservation.status
        reservation.status = new_status
        if new_status == "completada":
            _consume_reserved(db, reservation)
        if new_status in ("cancelada", "completada", "reembolsada", "devuelta") and old_status not in ("cancelada", "completada", "reembolsada", "devuelta"):
            _release_reserved(db, reservation)
        if new_status in ("reembolsada", "devuelta") and old_status == "completada":
            _restore_consumed(db, reservation)
    db.commit()
    db.refresh(reservation)
    return reservation


def delete_reservation(db: Session, reservation_id: int) -> None:
    reservation = get_reservation(db, reservation_id)
    if reservation.status not in ("cancelada", "completada"):
        _release_reserved(db, reservation)
    db.delete(reservation)
    db.commit()


def get_receipt(db: Session, sale_id: int) -> ReceiptResponse:
    sale = get_sale(db, sale_id)
    status = sale.payments[-1].status if sale.payments else PaymentStatus.PENDIENTE.value
    return ReceiptResponse(
        sale_id=sale.id, receipt_number=f"REC-{sale.id:012d}",
        invoice_number=f"FAC-{sale.id:012d}", sale_date=sale.sale_date,
        sale_type=sale.sale_type, branch_id=sale.branch_id, client_id=sale.client_id,
        subtotal=sale.total, total=sale.total, payment_status=status,
        items=[{"id": i.id, "stock_id": i.stock_id, "quantity": i.quantity, "unit_price": i.unit_price} for i in sale.items],
    )