from datetime import date as DateType

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.models.user import Role, User
from app.schemas.commerce import (
    CartItemRequest,
    CartItemUpdate,
    CartResponse,
    CheckoutRequest,
    CustomerDeliveryConfirmation,
    DeliveryStatusUpdate,
    InvoiceResponse,
    PosSaleCreate,
    QrPaymentRequest,
    QrPaymentResponse,
    ReservationCreate,
    ReservationResponse,
    ReservationStatus,
    ReservationUpdate,
    SaleResponse,
    ReceiptResponse,
)
from app.services import commerce_service
from app.services.invoice_pdf import build_invoice_pdf
from app.providers import get_payment_provider, get_fiscal_provider, get_notification_provider

router = APIRouter(prefix='/commerce', tags=['commerce'])
staff = Depends(require_role(Role.ADMINISTRADOR, Role.ENCARGADO, Role.CAJERO))
PRIVILEGED = (Role.ADMINISTRADOR, Role.ENCARGADO, Role.CAJERO)
RESERVATION_STAFF = (Role.ENCARGADO, Role.CAJERO)


@router.post('/payments/stripe/webhook', include_in_schema=False)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    event = get_payment_provider("stripe").verify_webhook(payload, signature)
    commerce_service.apply_payment_event(db, event)
    return {"received": True}


@router.post('/sales/{sale_id}/invoice', response_model=InvoiceResponse)
def issue_invoice(sale_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sale = commerce_service.get_sale(db, sale_id)
    if user.role != Role.SUPERADMIN and user.tenant_id is not None and sale.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail='Sale not found')
    if user.role not in PRIVILEGED and sale.client_id != user.id:
        raise HTTPException(status_code=403, detail='Insufficient permissions')
    return get_fiscal_provider().issue_invoice(sale=sale)


@router.get('/sales/{sale_id}/invoice.pdf')
def download_invoice_pdf(
    sale_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Factura en PDF (documento fiscal simulado del CU11).

    Usa el mismo documento que `POST /sales/{id}/invoice`, así que el número, el IVA y
    el descargo del PDF coinciden con la respuesta JSON.
    """
    sale = commerce_service.get_sale(db, sale_id)
    if user.role != Role.SUPERADMIN and user.tenant_id is not None and sale.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail='Sale not found')
    if user.role not in PRIVILEGED and sale.client_id != user.id:
        raise HTTPException(status_code=403, detail='Insufficient permissions')
    invoice = get_fiscal_provider().issue_invoice(sale=sale)
    pdf = build_invoice_pdf(invoice, commerce_service.sale_lines(db, sale_id))
    filename = f"{invoice.get('invoice_number', f'FAC-{sale_id:012d}')}.pdf"
    return Response(
        content=pdf,
        media_type='application/pdf',
        headers={'Content-Disposition': f'inline; filename="{filename}"'},
    )


@router.post('/sales/{sale_id}/notifications')
def send_sale_notification(sale_id: int, channel: str = "email",
                           user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sale = commerce_service.get_sale(db, sale_id)
    if user.role != Role.SUPERADMIN and user.tenant_id is not None and sale.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail='Sale not found')
    if user.role not in PRIVILEGED and sale.client_id != user.id:
        raise HTTPException(status_code=403, detail='Insufficient permissions')
    payment = sale.payments[-1] if sale.payments else None
    return get_notification_provider().send(
        event="sale.updated",
        sale_id=sale.id,
        channel=channel,
        status="aprobado" if payment and payment.status == "completado" else "pendiente",
        total=sale.total,
        reference=payment.reference if payment else None,
        invoice_number=f"FAC-{sale.id:012d}",
    )


@router.post('/payments/qr', response_model=QrPaymentResponse)
def create_qr_payment(
    data: QrPaymentRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    amount = data.amount
    if amount is None:
        cart = commerce_service.get_cart(db, user.id)
        amount = cart.total if cart.total > 0 else Decimal("50.00")
    return commerce_service.generate_qr_payment(amount=amount, currency=data.currency)


@router.get('/cart', response_model=CartResponse)
def get_cart(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return commerce_service.get_cart(db, user.id)


@router.post('/cart/items', response_model=CartResponse, status_code=201)
def add_cart_item(
    data: CartItemRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return commerce_service.add_to_cart(db, user.id, data)


@router.patch('/cart/items/{item_id}', response_model=CartResponse)
def edit_cart_item(
    item_id: int,
    data: CartItemUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return commerce_service.update_cart_item(db, user.id, item_id, data.quantity)


@router.delete('/cart/items/{item_id}', response_model=CartResponse)
def remove_cart_item(
    item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return commerce_service.remove_cart_item(db, user.id, item_id)


@router.post('/cart/checkout', response_model=SaleResponse, status_code=201)
def buy_cart(
    data: CheckoutRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    sale = commerce_service.checkout(db, user.id, data)
    return commerce_service.sale_response(db, sale)


@router.get('/sales', response_model=list[SaleResponse])
def sales_history(
    client_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role not in PRIVILEGED:
        return commerce_service.list_sales(db, user.id, tenant_id=user.tenant_id)
    return commerce_service.list_sales(db, client_id, tenant_id=user.tenant_id)


@router.get('/sales/{sale_id}', response_model=SaleResponse)
def get_sale(sale_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sale = commerce_service.get_sale(db, sale_id)
    if user.role != Role.SUPERADMIN and user.tenant_id is not None and sale.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail='Sale not found')
    if user.role not in PRIVILEGED and sale.client_id != user.id:
        raise HTTPException(status_code=403, detail='Insufficient permissions')
    return commerce_service.sale_response(db, sale)


@router.get('/sales/{sale_id}/receipt', response_model=ReceiptResponse)
def sale_receipt(sale_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sale = commerce_service.get_sale(db, sale_id)
    if user.role != Role.SUPERADMIN and user.tenant_id is not None and sale.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail='Sale not found')
    if user.role not in PRIVILEGED and sale.client_id != user.id:
        raise HTTPException(status_code=403, detail='Insufficient permissions')
    return commerce_service.get_receipt(db, sale_id)


@router.post('/sales/pos', response_model=SaleResponse, status_code=201, dependencies=[staff])
def register_pos_sale(
    data: PosSaleCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    from app.models.branch import Branch
    branch = db.get(Branch, data.branch_id)
    if not branch:
        raise HTTPException(404, "Branch not found")
    if user.role != Role.SUPERADMIN and user.tenant_id is not None and branch.tenant_id != user.tenant_id:
        raise HTTPException(403, "Branch does not belong to user tenant")
    sale = commerce_service.pos_sale(db, user.id, data)
    return commerce_service.sale_response(db, sale)


@router.get('/reservations', response_model=list[ReservationResponse])
def list_reservations(
    status: ReservationStatus | None = None,
    branch_id: int | None = None,
    reservation_date: DateType | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role not in RESERVATION_STAFF:
        return commerce_service.list_reservations(db, user.id, status.value if status else None, branch_id, reservation_date, tenant_id=user.tenant_id)
    return commerce_service.list_reservations(db, None, status.value if status else None, branch_id, reservation_date, tenant_id=user.tenant_id)


@router.post('/reservations', response_model=ReservationResponse, status_code=201)
def create_reservation(
    data: ReservationCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    from app.models.branch import Branch
    branch = db.get(Branch, data.branch_id)
    if not branch:
        raise HTTPException(404, "Branch not found")
    if user.role != Role.SUPERADMIN and user.tenant_id is not None and branch.tenant_id != user.tenant_id:
        raise HTTPException(403, "Branch does not belong to user tenant")
    return commerce_service.create_reservation(db, user.id, data)


@router.get('/reservations/{reservation_id}', response_model=ReservationResponse)
def get_reservation(
    reservation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    reservation = commerce_service.get_reservation(db, reservation_id)
    if user.role != Role.SUPERADMIN and user.tenant_id is not None and reservation.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail='Reservation not found')
    if user.role not in RESERVATION_STAFF and reservation.client_id != user.id:
        raise HTTPException(status_code=403, detail='Insufficient permissions')
    return reservation


@router.patch('/reservations/{reservation_id}', response_model=ReservationResponse)
def update_reservation(
    reservation_id: int,
    data: ReservationUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reservation = commerce_service.get_reservation(db, reservation_id)
    if user.role != Role.SUPERADMIN and user.tenant_id is not None and reservation.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail='Reservation not found')
    if user.role not in RESERVATION_STAFF:
        if reservation.client_id != user.id:
            raise HTTPException(status_code=403, detail='Insufficient permissions')
        if data.status is not None and data.status is not ReservationStatus.CANCELADA:
            raise HTTPException(status_code=403, detail='Clients can only cancel their reservations')
    return commerce_service.update_reservation(db, reservation_id, data)


@router.delete('/reservations/{reservation_id}', status_code=204)
def delete_reservation(
    reservation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    reservation = commerce_service.get_reservation(db, reservation_id)
    if user.role != Role.SUPERADMIN and user.tenant_id is not None and reservation.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail='Reservation not found')
    if user.role not in RESERVATION_STAFF and reservation.client_id != user.id:
        raise HTTPException(status_code=403, detail='Insufficient permissions')
    commerce_service.delete_reservation(db, reservation_id)


@router.post('/reservations/{reservation_id}/cancel', response_model=ReservationResponse)
def cancel_reservation(
    reservation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Cancela una reserva y libera inmediatamente el stock reservado para que vuelva a estar a la venta.
    Puede ser ejecutado por el propio cliente o por el personal de tienda.
    """
    reservation = commerce_service.get_reservation(db, reservation_id)
    if user.role != Role.SUPERADMIN and user.tenant_id is not None and reservation.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail='Reservation not found')
    if user.role not in RESERVATION_STAFF and reservation.client_id != user.id:
        raise HTTPException(status_code=403, detail='Insufficient permissions')
    return commerce_service.cancel_reservation(db, reservation_id)


@router.post('/reservations/{reservation_id}/complete', response_model=SaleResponse)
def complete_reservation(
    reservation_id: int,
    user: User = Depends(require_role(Role.ADMINISTRADOR, Role.ENCARGADO, Role.CAJERO)),
    db: Session = Depends(get_db),
):
    """
    Convierte una reserva en una venta formal de contado cuando el cliente se presenta a retirar la prenda.
    Descuenta definitivamente el stock físico y completa la reserva.
    """
    reservation = commerce_service.get_reservation(db, reservation_id)
    if user.role != Role.SUPERADMIN and user.tenant_id is not None and reservation.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail='Reservation not found')
    sale = commerce_service.convert_reservation_to_sale(db, reservation_id, cashier_id=user.id)
    return commerce_service.sale_response(db, sale)


@router.patch('/sales/{sale_id}/delivery-status', response_model=SaleResponse, dependencies=[staff])
def update_sale_delivery_status(
    sale_id: int,
    data: DeliveryStatusUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Actualiza el estado logístico de despacho de la venta (Pagado -> Por despachar -> Enviado -> Entregado).
    Permitido para personal de administración, encargado o cajero.
    """
    sale = commerce_service.get_sale(db, sale_id)
    if user.role != Role.SUPERADMIN and user.tenant_id is not None and sale.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail='Sale not found')
    sale = commerce_service.update_delivery_status(db, sale_id, data.delivery_status, data.notes)
    return commerce_service.sale_response(db, sale)


@router.post('/sales/{sale_id}/confirm-delivery', response_model=SaleResponse)
def confirm_delivery_by_customer(
    sale_id: int,
    data: CustomerDeliveryConfirmation,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Permite al cliente final confirmar en su aplicación móvil o web la recepción conforme de la prenda entregada.
    """
    sale = commerce_service.get_sale(db, sale_id)
    if user.role != Role.SUPERADMIN and user.tenant_id is not None and sale.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail='Sale not found')
    sale = commerce_service.confirm_customer_delivery(db, sale_id, user.id, data.notes)
    return commerce_service.sale_response(db, sale)