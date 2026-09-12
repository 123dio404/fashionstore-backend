from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

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
from app.models.user import User
from app.schemas.commerce import (
    CartItemRequest,
    CartItemResponse,
    CartResponse,
    CheckoutRequest,
    PosSaleCreate,
    ReservationCreate,
    ReservationUpdate,
)


def _stock(db: Session, stock_id: UUID) -> Stock:
    stock = db.get(Stock, stock_id)
    if stock is None:
        raise HTTPException(404, "Stock record not found")
    return stock


def get_or_create_cart(db: Session, user_id: UUID) -> Cart:
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


def get_cart(db: Session, user_id: UUID) -> CartResponse:
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


def add_to_cart(db: Session, user_id: UUID, data: CartItemRequest) -> CartResponse:
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


def update_cart_item(db: Session, user_id: UUID, item_id: UUID, quantity: int) -> CartResponse:
    cart = get_or_create_cart(db, user_id)
    item = next((i for i in cart.items if i.id == item_id), None)
    if item is None:
        raise HTTPException(404, "Cart item not found")
    if quantity > (item.stock.physical_stock - item.stock.reserved_stock):
        raise HTTPException(409, "Requested quantity exceeds available stock")
    item.quantity = quantity
    db.commit()
    return get_cart(db, user_id)


def remove_cart_item(db: Session, user_id: UUID, item_id: UUID) -> CartResponse:
    cart = get_or_create_cart(db, user_id)
    item = next((i for i in cart.items if i.id == item_id), None)
    if item is None:
        raise HTTPException(404, "Cart item not found")
    db.delete(item)
    db.commit()
    return get_cart(db, user_id)


def checkout(db: Session, user_id: UUID, data: CheckoutRequest) -> Sale:
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
    sale = Sale(client_id=user_id, user_id=user_id, branch_id=data.branch_id, total=total, sale_type="digital")
    for ci in cart.items:
        ci.stock.physical_stock -= ci.quantity
        sale.items.append(SaleItem(stock_id=ci.stock_id, quantity=ci.quantity, unit_price=ci.price))
        db.add(
            InventoryMovement(
                movement_type=MovementType.VENTA,
                variant_id=ci.stock.variant_id,
                destination_branch_id=data.branch_id,
                quantity=-ci.quantity,
                reason="Venta digital",
                performed_by_id=user_id,
            )
        )
    db.add(sale)
    db.flush()
    sale.payments.append(
        SalePayment(
            amount=total,
            status="completado",
            paid_at=datetime.now(timezone.utc),
            reference=f"ORD-{sale.id.hex[:12].upper()}",
        )
    )
    cart.status = "completado"
    db.commit()
    db.refresh(sale)
    return sale


def get_sale(db: Session, sale_id: UUID) -> Sale:
    sale = db.get(Sale, sale_id)
    if sale is None:
        raise HTTPException(404, "Sale not found")
    return sale


def list_sales(db: Session, client_id: UUID | None = None) -> list[Sale]:
    q = select(Sale).order_by(Sale.sale_date.desc(), Sale.id)
    if client_id is not None:
        q = q.where(Sale.client_id == client_id)
    return list(db.scalars(q).all())


def pos_sale(db: Session, user_id: UUID, data: PosSaleCreate) -> Sale:
    if db.get(Branch, data.branch_id) is None:
        raise HTTPException(404, "Branch not found")
    if data.client_id is not None and db.get(User, data.client_id) is None:
        raise HTTPException(404, "Client not found")
    total = Decimal("0")
    entries = []
    for inp in data.items:
        stock = _stock(db, inp.stock_id)
        if inp.quantity > (stock.physical_stock - stock.reserved_stock):
            raise HTTPException(409, f"Insufficient available stock for {inp.stock_id}")
        unit_price = stock.variant.product.price
        total += unit_price * inp.quantity
        entries.append((stock, inp.quantity, unit_price))
    if total <= 0:
        raise HTTPException(400, "Sale total must be positive")
    sale = Sale(client_id=data.client_id, user_id=user_id, branch_id=data.branch_id, total=total, sale_type="pos")
    for stock, quantity, unit_price in entries:
        stock.physical_stock -= quantity
        sale.items.append(SaleItem(stock_id=stock.id, quantity=quantity, unit_price=unit_price))
        db.add(
            InventoryMovement(
                movement_type=MovementType.VENTA,
                variant_id=stock.variant_id,
                destination_branch_id=data.branch_id,
                quantity=-quantity,
                reason="Venta POS",
                performed_by_id=user_id,
            )
        )
    db.add(sale)
    db.flush()
    if data.paid:
        sale.payments.append(
            SalePayment(
                amount=total,
                status="completado",
                paid_at=datetime.now(timezone.utc),
                reference=f"POS-{sale.id.hex[:12].upper()}",
            )
        )
    db.commit()
    db.refresh(sale)
    return sale


def create_reservation(db: Session, user_id: UUID, data: ReservationCreate) -> Reservation:
    if db.get(Branch, data.branch_id) is None:
        raise HTTPException(404, "Branch not found")
    entries = []
    for inp in data.items:
        stock = _stock(db, inp.stock_id)
        if inp.quantity > (stock.physical_stock - stock.reserved_stock):
            raise HTTPException(409, f"Insufficient available stock for {inp.stock_id}")
        entries.append((stock, inp.quantity))
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
                variant_id=stock.variant_id,
                destination_branch_id=data.branch_id,
                quantity=quantity,
                reason="Reserva probador",
                performed_by_id=user_id,
            )
        )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    return reservation


def get_reservation(db: Session, reservation_id: UUID) -> Reservation:
    reservation = db.get(Reservation, reservation_id)
    if reservation is None:
        raise HTTPException(404, "Reservation not found")
    return reservation


def list_reservations(
    db: Session,
    client_id: UUID | None = None,
    status: str | None = None,
    branch_id: UUID | None = None,
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
                    variant_id=stock.variant_id,
                    destination_branch_id=reservation.branch_id,
                    quantity=-item.quantity,
                    reason="Liberación reserva",
                    performed_by_id=reservation.client_id,
                )
            )


def update_reservation(db: Session, reservation_id: UUID, data: ReservationUpdate) -> Reservation:
    reservation = get_reservation(db, reservation_id)
    values = data.model_dump(exclude_unset=True)
    new_status = values.pop("status", None)
    for k, v in values.items():
        setattr(reservation, k, v)
    if new_status is not None and new_status != reservation.status:
        old_status = reservation.status
        reservation.status = new_status
        if new_status in ("cancelada", "completada") and old_status not in ("cancelada", "completada"):
            _release_reserved(db, reservation)
    db.commit()
    db.refresh(reservation)
    return reservation


def delete_reservation(db: Session, reservation_id: UUID) -> None:
    reservation = get_reservation(db, reservation_id)
    if reservation.status not in ("cancelada", "completada"):
        _release_reserved(db, reservation)
    db.delete(reservation)
    db.commit()