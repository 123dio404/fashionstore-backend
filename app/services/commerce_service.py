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
    ReservationResponse,
    ReservationUpdate,
    PaymentStatus,
    ReceiptResponse,
    SaleItemResponse,
    SalePaymentResponse,
    SaleResponse,
)
from app.providers import IN_STORE_PAYMENT_METHODS, get_payment_provider, get_notification_provider
from app.core.config import settings


class MockPaymentProvider:
    """Deterministic provider used by the API until a real gateway is configured."""

    def charge(self, amount: Decimal, status: PaymentStatus, reference: str | None = None) -> dict:
        return {
            "status": status.value,
            "reference": reference,
            "paid_at": datetime.now(timezone.utc) if status == PaymentStatus.COMPLETADO else None,
        }


PAYMENT_PROVIDERS = {"mock": MockPaymentProvider()}


def _notify_critical_stock(db: Session, branch: Branch, stock: Stock) -> None:
    """Dispara automáticamente una notificación de stock crítico al Administrador de la tienda (Punto 3)."""
    try:
        from app.models.notification import Notification
        from app.models.product import ProductVariant
        variant = db.get(ProductVariant, stock.variant_id)
        prod_name = variant.product.name if variant and variant.product else f"Prenda #{stock.variant_id}"
        size_name = variant.size.name if variant and variant.size else ""
        color_name = variant.color.name if variant and variant.color else ""
        notif = Notification(
            tenant_id=branch.tenant_id,
            target_role="Administrador",
            title="⚠️ Alerta de Stock Crítico",
            message=f"La prenda '{prod_name}' (Talla {size_name}, Color {color_name}) en la sucursal '{branch.name}' tiene solo {stock.physical_stock} unidades disponibles. Se sugiere reposición urgente.",
            type="system",
            link="/admin/inventory",
            is_read=False,
        )
        db.add(notif)
    except Exception:
        pass


def _stock(db: Session, stock_id: int) -> Stock:
    stock = db.get(Stock, stock_id)
    if stock is None:
        raise HTTPException(404, "Stock record not found")
    return stock


def calculate_item_unit_price(product, quantity: int) -> tuple[Decimal, bool]:
    """
    Calcula el precio unitario considerando:
    1. Liquidación de fin de temporada (is_clearance) con discount_percentage (ej. 40% o 60%).
    2. Precio al por mayor si quantity >= product.wholesale_min_quantity y wholesale_price está definido.
    3. Precio unitario regular por menor (product.price).
    Retorna: (precio_final, es_precio_mayorista)
    """
    base_price = product.price
    # 1. Liquidación fin de temporada (recuperación de capital según audio)
    if getattr(product, "is_clearance", False) and getattr(product, "discount_percentage", Decimal("0.00")) > Decimal("0.00"):
        factor = Decimal("1.00") - (Decimal(str(product.discount_percentage)) / Decimal("100.00"))
        base_price = (base_price * factor).quantize(Decimal("0.01"))

    # 2. Precio al por mayor por volumen automático (ej. a partir de 3 prendas)
    wholesale_price = getattr(product, "wholesale_price", None)
    min_qty = getattr(product, "wholesale_min_quantity", 3) or 3
    if wholesale_price is not None and quantity >= min_qty:
        return (wholesale_price, True)

    return (base_price, False)


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
        # Recalcular precio unitario automáticamente según volumen acumulado
        computed_price, is_ws = calculate_item_unit_price(product, ci.quantity)
        if ci.price != computed_price:
            ci.price = computed_price
        total += ci.price * ci.quantity
        items.append(
            CartItemResponse(
                id=ci.id,
                stock_id=ci.stock_id,
                quantity=ci.quantity,
                price=ci.price,
                is_wholesale_applied=is_ws,
                wholesale_min_qty=getattr(product, "wholesale_min_quantity", 3) or 3,
                variant_id=variant.id,
                product_id=product.id,
                product_name=product.name,
                size=variant.size.name if variant.size else None,
                color=variant.color.name if variant.color else None,
            )
        )
    db.commit()
    return CartResponse(id=cart.id, status=cart.status, items=items, total=total)


def add_to_cart(db: Session, user_id: int, data: CartItemRequest) -> CartResponse:
    stock = _stock(db, data.stock_id)
    available = stock.physical_stock - stock.reserved_stock
    if available <= 0:
        raise HTTPException(409, "Stock not available")
    user = db.get(User, user_id)
    if user and user.tenant_id is not None and stock.variant.product.tenant_id != user.tenant_id:
        raise HTTPException(403, "Product does not belong to user tenant")
    cart = get_or_create_cart(db, user_id)
    existing = next((i for i in cart.items if i.stock_id == data.stock_id), None)
    quantity = data.quantity + (existing.quantity if existing else 0)
    if quantity > available:
        raise HTTPException(409, "Requested quantity exceeds available stock")
    
    product = stock.variant.product
    unit_price, _ = calculate_item_unit_price(product, quantity)
    if existing:
        existing.quantity = quantity
        existing.price = unit_price
    else:
        cart.items.append(
            CartItem(stock_id=data.stock_id, quantity=data.quantity, price=unit_price)
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
    product = item.stock.variant.product
    unit_price, _ = calculate_item_unit_price(product, quantity)
    item.price = unit_price
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
    branch = db.get(Branch, data.branch_id)
    if branch is None:
        raise HTTPException(404, "Branch not found")
    if branch.tenant and branch.tenant.status == "Suspendido":
        raise HTTPException(
            status_code=403,
            detail="Operación bloqueada: La empresa se encuentra suspendida por falta de pago de suscripción SaaS.",
        )
    user = db.get(User, user_id)
    if user and user.tenant_id is not None and branch.tenant_id != user.tenant_id:
        raise HTTPException(403, "Branch does not belong to user tenant")
    cart = db.scalar(
        select(Cart).where(Cart.user_id == user_id, Cart.status == "activo").with_for_update()
    ) or get_or_create_cart(db, user_id)
    if not cart.items:
        raise HTTPException(400, "Cart is empty")
    total = Decimal("0")
    locked_items = []
    for ci in cart.items:
        stock = db.scalar(select(Stock).where(Stock.id == ci.stock_id).with_for_update())
        if stock is None or ci.quantity > stock.physical_stock - stock.reserved_stock:
            raise HTTPException(409, f"Insufficient stock for {ci.stock_id}")
        locked_items.append((ci, stock))
        total += ci.price * ci.quantity
    sale = Sale(
        tenant_id=branch.tenant_id,
        client_id=user_id,
        user_id=user_id,
        branch_id=data.branch_id,
        total=total,
        sale_type="digital",
        tax_id=data.tax_id or "0",
        business_name=data.business_name or "Consumidor Final",
    )
    db.add(sale)
    db.flush()
    provider = get_payment_provider(data.payment_provider)
    intent = provider.create_intent(
        total,
        "usd",
        data.idempotency_key or f"sale-{sale.id}",
        {
            "sale_id": sale.id,
            "card_token": data.card_token,
            "simulate_rejection": data.simulate_rejection,
        },
    )
    intent_status = intent.get("status")
    if intent_status == "succeeded":
        status = PaymentStatus.COMPLETADO.value
    elif intent_status in {"failed", "declined"}:
        status = PaymentStatus.FALLIDO.value
    else:
        status = PaymentStatus.PENDIENTE.value

    payment_ref = intent.get("id") or data.payment_reference
    sale.payments.append(
        SalePayment(
            amount=total,
            status=status,
            paid_at=datetime.now(timezone.utc) if status == PaymentStatus.COMPLETADO.value else None,
            reference=payment_ref,
        )
    )

    if status == PaymentStatus.COMPLETADO.value:
        for ci, stock in locked_items:
            stock.physical_stock -= ci.quantity
            sale.items.append(SaleItem(stock_id=ci.stock_id, quantity=ci.quantity, unit_price=ci.price))
            db.add(InventoryMovement(movement_type=MovementType.VENTA, inventory_id=stock.id, quantity=-ci.quantity, reason="Venta digital"))
            if stock.physical_stock <= 2:
                _notify_critical_stock(db, branch, stock)
        cart.status = "completado"
        db.commit()
        db.refresh(sale)
        # Notificación exitosa
        get_notification_provider().send(
            event="sale.completed",
            sale_id=sale.id,
            channel="in_app",
            status="aprobado",
            total=total,
            reference=payment_ref,
            payment_method=data.payment_provider,
            invoice_number=f"FAC-{sale.id:012d}",
        )
        return sale
    elif status == PaymentStatus.FALLIDO.value:
        # Pago rechazado: No descontar inventario, dejar carrito intacto
        db.commit()
        db.refresh(sale)
        error_msg = intent.get("error_message") or "Pago rechazado por la pasarela: Fondos insuficientes o tarjeta declinada."
        get_notification_provider().send(
            event="sale.rejected",
            sale_id=sale.id,
            channel="in_app",
            status="rechazado",
            total=total,
            reference=payment_ref,
            payment_method=data.payment_provider,
            invoice_number=f"FAC-{sale.id:012d}",
        )
        raise HTTPException(status_code=402, detail=error_msg)
    else:
        db.commit()
        db.refresh(sale)
        return sale


def generate_qr_payment(amount: Decimal = Decimal("50.00"), currency: str = "usd") -> dict:
    from app.providers.payments import generate_qr_base64
    ref = f"STRIPE-QR-{int(datetime.now(timezone.utc).timestamp() * 1000)}"
    payment_url = f"https://checkout.stripe.com/pay/{ref}"
    qr_b64 = generate_qr_base64(payment_url)
    return {
        "reference": ref,
        "qr_code_base64": qr_b64,
        "payment_url": payment_url,
        "amount": amount,
        "currency": currency,
    }


def apply_payment_event(db: Session, event: dict) -> Sale | None:
    obj = event.get("data", {}).get("object", {})
    intent_id = obj.get("id")
    if not intent_id:
        return None
    sale = db.scalar(select(Sale).join(SalePayment).where(SalePayment.reference == intent_id).with_for_update())
    if sale is None or not sale.payments:
        return None
    payment = sale.payments[-1]
    event_type = event.get("type", "")
    if event_type == "payment_intent.succeeded" and payment.status != PaymentStatus.COMPLETADO.value:
        cart = db.scalar(select(Cart).where(Cart.user_id == sale.client_id, Cart.status == "activo").with_for_update())
        if cart:
            for ci in cart.items:
                stock = db.scalar(select(Stock).where(Stock.id == ci.stock_id).with_for_update())
                if stock is None or ci.quantity > stock.available_stock:
                    payment.status = PaymentStatus.FALLIDO.value
                    db.commit()
                    return sale
                stock.physical_stock -= ci.quantity
                sale.items.append(SaleItem(stock_id=ci.stock_id, quantity=ci.quantity, unit_price=ci.price))
                db.add(InventoryMovement(movement_type=MovementType.VENTA, inventory_id=stock.id, quantity=-ci.quantity, reason="Stripe payment"))
            cart.status = "completado"
        payment.status = PaymentStatus.COMPLETADO.value
        payment.paid_at = datetime.now(timezone.utc)
    elif event_type in {"payment_intent.payment_failed", "payment_intent.canceled"}:
        payment.status = PaymentStatus.FALLIDO.value
    elif event_type == "charge.refunded":
        if payment.status == PaymentStatus.COMPLETADO.value:
            for item in sale.items:
                stock = db.scalar(select(Stock).where(Stock.id == item.stock_id).with_for_update())
                if stock is not None:
                    stock.physical_stock += item.quantity
                    db.add(InventoryMovement(
                        movement_type=MovementType.AJUSTE,
                        inventory_id=stock.id,
                        quantity=item.quantity,
                        reason="Stripe refund",
                    ))
        payment.status = PaymentStatus.REEMBOLSADO.value
    db.commit()
    db.refresh(sale)
    return sale


def get_sale(db: Session, sale_id: int) -> Sale:
    sale = db.get(Sale, sale_id)
    if sale is None:
        raise HTTPException(404, "Sale not found")
    return sale


def sale_lines(db: Session, sale_id: int) -> list[dict]:
    """Detalle de la venta con el nombre de la prenda, la talla y el color.

    Lo consume la factura en PDF: `detalle_venta` guarda la fila de inventario, así
    que hay que subir por variante → producto para imprimir algo legible.
    """
    sale = get_sale(db, sale_id)
    lines: list[dict] = []
    for item in sale.items:
        stock = db.get(Stock, item.stock_id)
        variant = stock.variant if stock is not None else None
        product = variant.product if variant is not None else None
        lines.append(
            {
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "name": product.name if product is not None else f"Artículo #{item.stock_id}",
                "brand": product.brand if product is not None else None,
                "size": variant.size.name if variant is not None and variant.size else None,
                "color": variant.color.name if variant is not None and variant.color else None,
            }
        )
    return lines


def list_sales(db: Session, client_id: int | None = None, tenant_id: int | None = None) -> list[SaleResponse]:
    q = select(Sale).order_by(Sale.sale_date.desc(), Sale.id)
    if client_id is not None:
        q = q.where(Sale.client_id == client_id)
    if tenant_id is not None:
        q = q.where(Sale.tenant_id == tenant_id)
    return [sale_response(db, sale) for sale in db.scalars(q).all()]


def sale_items(db: Session, sale: Sale) -> list[SaleItemResponse]:
    """Detalle de cada línea con variante → producto, igual que la factura en PDF."""
    rows: list[SaleItemResponse] = []
    for item in sale.items:
        stock = db.get(Stock, item.stock_id)
        variant = stock.variant if stock is not None else None
        product = variant.product if variant is not None else None
        rows.append(
            SaleItemResponse(
                id=item.id,
                stock_id=item.stock_id,
                quantity=item.quantity,
                unit_price=item.unit_price,
                variant_id=variant.id if variant is not None else None,
                product_id=product.id if product is not None else None,
                product_name=product.name if product is not None else None,
                brand=product.brand if product is not None else None,
                size=variant.size.name if variant is not None and variant.size else None,
                color=variant.color.name if variant is not None and variant.color else None,
            )
        )
    return rows


def sale_response(db: Session, sale: Sale) -> SaleResponse:
    """Venta lista para el cliente: líneas legibles, pagos y estado de despacho."""
    st = sale.sale_type or "pos"
    if st not in ("digital", "pos"):
        st = "digital" if "digital" in str(st).lower() else "pos"
    return SaleResponse(
        id=sale.id,
        client_id=sale.client_id,
        user_id=sale.user_id,
        branch_id=sale.branch_id,
        sale_date=sale.sale_date,
        total=sale.total,
        sale_type=st,
        delivery_status=getattr(sale, "delivery_status", "PAGADO") or "PAGADO",
        customer_notes=getattr(sale, "customer_notes", None),
        tax_id=getattr(sale, "tax_id", None) or "0",
        business_name=getattr(sale, "business_name", None) or "Consumidor Final",
        delivered_at=getattr(sale, "delivered_at", None),
        items=sale_items(db, sale),
        payments=[SalePaymentResponse.model_validate(p) for p in sale.payments],
    )


def pos_sale(db: Session, user_id: int, data: PosSaleCreate) -> Sale:
    branch = db.get(Branch, data.branch_id)
    if branch is None:
        raise HTTPException(404, "Branch not found")
    if branch.tenant and branch.tenant.status == "Suspendido":
        raise HTTPException(
            status_code=403,
            detail="Operación bloqueada: La empresa se encuentra suspendida por falta de pago de suscripción SaaS.",
        )
    client = db.get(User, data.client_id)
    if client is None:
        raise HTTPException(404, "Client not found")
    total = Decimal("0")
    entries = []
    for inp in data.items:
        stock = _stock(db, inp.stock_id)
        if stock.branch_id != data.branch_id:
            raise HTTPException(422, f"Stock {inp.stock_id} does not belong to the sale branch")
        if inp.quantity > (stock.physical_stock - stock.reserved_stock):
            raise HTTPException(409, f"Insufficient available stock for {inp.stock_id}")
        product = stock.variant.product
        unit_price, _ = calculate_item_unit_price(product, inp.quantity)
        total += unit_price * inp.quantity
        entries.append((stock, inp.quantity, unit_price))
    if total <= 0:
        raise HTTPException(400, "Sale total must be positive")
    requested_status = data.payment_status or (
        PaymentStatus.COMPLETADO if data.paid else PaymentStatus.PENDIENTE
    )
    sale = Sale(
        tenant_id=branch.tenant_id,
        client_id=data.client_id,
        user_id=user_id,
        branch_id=data.branch_id,
        total=total,
        sale_type="pos",
        tax_id=data.tax_id or "0",
        business_name=data.business_name or "Consumidor Final",
    )
    db.add(sale)
    db.flush()
    provider_name = (data.payment_provider or settings.payment_provider).casefold()
    if provider_name in IN_STORE_PAYMENT_METHODS:
        # RF18: el cobro en caja no pasa por pasarela. El cajero confirma el pago (efectivo,
        # tarjeta o datáfono), el estado lo fijan `paid`/`payment_status` y la referencia es el
        # comprobante interno POS-<venta>.
        intent = get_payment_provider(provider_name).create_intent(
            total, "usd", data.payment_reference or f"pos-{sale.id}", {"sale_id": sale.id}
        )
        payment_status, reference = requested_status.value, intent.get("id")
    elif provider_name == "mock":
        if settings.environment.casefold() not in {"development", "test"}:
            raise HTTPException(400, "Mock payment provider is only available in development or test")
        payment = PAYMENT_PROVIDERS["mock"].charge(total, requested_status, data.payment_reference)
        payment_status, reference = payment["status"], payment["reference"]
    else:
        intent = get_payment_provider(provider_name).create_intent(
            total, "usd", data.payment_reference or f"pos-{sale.id}", {"sale_id": sale.id}
        )
        payment_status = PaymentStatus.COMPLETADO.value if intent.get("status") == "succeeded" else PaymentStatus.PENDIENTE.value
        reference = intent.get("id")
    sale.payments.append(SalePayment(amount=total, status=payment_status,
                                     paid_at=datetime.now(timezone.utc) if payment_status == PaymentStatus.COMPLETADO.value else None,
                                     reference=reference))
    if payment_status != PaymentStatus.COMPLETADO.value:
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
        if stock.physical_stock <= 2:
            _notify_critical_stock(db, branch, stock)
    db.add(sale)
    db.flush()
    if sale.payments[0].reference is None:
        sale.payments[0].reference = f"POS-{sale.id:012d}"
    db.commit()
    db.refresh(sale)
    return sale


def create_reservation(db: Session, user_id: int, data: ReservationCreate) -> Reservation:
    branch = db.get(Branch, data.branch_id)
    if branch is None:
        raise HTTPException(404, "Branch not found")
    user = db.get(User, user_id)
    if user and user.tenant_id is not None and branch.tenant_id != user.tenant_id:
        raise HTTPException(403, "Branch does not belong to user tenant")
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
        tenant_id=branch.tenant_id,
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
    tenant_id: int | None = None,
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
    if tenant_id is not None:
        q = q.where(Reservation.tenant_id == tenant_id)
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
        sale_id=sale.id,
        receipt_number=f"REC-{sale.id:012d}",
        invoice_number=f"FAC-{sale.id:012d}",
        sale_date=sale.sale_date,
        sale_type=sale.sale_type,
        branch_id=sale.branch_id,
        client_id=sale.client_id,
        tax_id=getattr(sale, "tax_id", None) or "0",
        business_name=getattr(sale, "business_name", None) or "Consumidor Final",
        subtotal=sale.total,
        total=sale.total,
        payment_status=status,
        items=sale_items(db, sale),
    )


def cancel_reservation(db: Session, reservation_id: int) -> Reservation:
    """Cancela una reserva y libera de inmediato el stock reservado para venta disponible."""
    reservation = get_reservation(db, reservation_id)
    if reservation.status in ("cancelada", "completada"):
        raise HTTPException(status_code=400, detail=f"No se puede cancelar una reserva en estado '{reservation.status}'")
    _release_reserved(db, reservation)
    reservation.status = "cancelada"
    db.commit()
    db.refresh(reservation)
    return reservation


def convert_reservation_to_sale(
    db: Session, reservation_id: int, cashier_id: int, payment_provider: str = "efectivo"
) -> Sale:
    """
    Convierte una reserva activa en una venta formal de contado cuando el cliente se presenta en tienda.
    Descuenta definitivamente el stock físico y libera la reserva.
    """
    reservation = get_reservation(db, reservation_id)
    if reservation.status in ("cancelada", "completada"):
        raise HTTPException(status_code=400, detail=f"Reserva en estado '{reservation.status}' no puede convertirse a venta")

    if reservation.branch and reservation.branch.tenant and reservation.branch.tenant.status == "Suspendido":
        raise HTTPException(
            status_code=403,
            detail="Operación bloqueada: La empresa se encuentra suspendida por falta de pago de suscripción SaaS.",
        )

    now = datetime.now(timezone.utc)
    # Consumir el stock reservado
    _consume_reserved(db, reservation)
    _release_reserved(db, reservation)
    reservation.status = "completada"
    reservation.checked_out_at = now

    # Calcular total y crear items de venta
    total = Decimal("0.00")
    sale_items_list: list[SaleItem] = []
    for item in reservation.items:
        stock = db.get(Stock, item.stock_id)
        unit_price = stock.variant.price if stock and stock.variant else Decimal("0.00")
        line_total = unit_price * item.quantity
        total += line_total
        sale_items_list.append(
            SaleItem(stock_id=item.stock_id, quantity=item.quantity, unit_price=unit_price)
        )
        if stock and stock.physical_stock <= 2:
            _notify_critical_stock(db, reservation.branch, stock)

    client_user = db.get(User, reservation.client_id)
    business_name = client_user.full_name if client_user else "Consumidor Final"

    sale = Sale(
        client_id=reservation.client_id,
        user_id=cashier_id,
        branch_id=reservation.branch_id,
        tenant_id=reservation.tenant_id,
        sale_date=now,
        total=total,
        sale_type="Reserva Entregada (Contado)",
        tax_id="0",
        business_name=business_name,
        items=sale_items_list,
        payments=[
            SalePayment(
                amount=total,
                status=PaymentStatus.COMPLETADO.value,
                paid_at=now,
                reference=f"RES-{reservation.id:08d}-SALE",
            )
        ],
    )
    db.add(sale)
    db.commit()
    db.refresh(sale)
    return sale


def update_delivery_status(db: Session, sale_id: int, delivery_status: str, notes: str | None = None) -> Sale:
    """
    Actualiza el estado de logística/entrega de la venta (RN audio: Pagado -> Por despachar -> Enviado -> Entregado).
    """
    valid_statuses = {"PAGADO", "POR_DESPACHAR", "ENVIADO", "ENTREGADO_CONFORME"}
    status_upper = delivery_status.upper().strip()
    if status_upper not in valid_statuses:
        raise HTTPException(400, f"Estado de entrega inválido. Valores permitidos: {', '.join(valid_statuses)}")
    sale = db.get(Sale, sale_id)
    if not sale:
        raise HTTPException(404, "Venta no encontrada")
    sale.delivery_status = status_upper
    if notes:
        sale.customer_notes = notes
    if status_upper == "ENTREGADO_CONFORME" and not sale.delivered_at:
        sale.delivered_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(sale)
    return sale


def confirm_customer_delivery(db: Session, sale_id: int, client_id: int, notes: str | None = None) -> Sale:
    """
    Permite al cliente confirmar en la app o web la recepción conforme de la prenda entregada.
    """
    sale = db.get(Sale, sale_id)
    if not sale:
        raise HTTPException(404, "Venta no encontrada")
    if sale.client_id != client_id:
        raise HTTPException(403, "No tiene permisos para confirmar la entrega de una compra de otro cliente")
    sale.delivery_status = "ENTREGADO_CONFORME"
    sale.delivered_at = datetime.now(timezone.utc)
    if notes:
        sale.customer_notes = f"Conformidad del cliente: {notes}"
    db.commit()
    db.refresh(sale)
    return sale