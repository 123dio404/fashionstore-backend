from datetime import date as DateType

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.models.user import Role, User
from app.schemas.commerce import (
    CartItemRequest,
    CartItemUpdate,
    CartResponse,
    CheckoutRequest,
    PosSaleCreate,
    ReservationCreate,
    ReservationResponse,
    ReservationStatus,
    ReservationUpdate,
    SaleResponse,
    ReceiptResponse,
)
from app.services import commerce_service
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


@router.post('/sales/{sale_id}/invoice')
def issue_invoice(sale_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sale = commerce_service.get_sale(db, sale_id)
    if user.role not in PRIVILEGED and sale.client_id != user.id:
        raise HTTPException(status_code=403, detail='Insufficient permissions')
    return get_fiscal_provider().issue_invoice(sale=sale)


@router.post('/sales/{sale_id}/notifications')
def send_sale_notification(sale_id: int, channel: str = "email",
                           user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sale = commerce_service.get_sale(db, sale_id)
    if user.role not in PRIVILEGED and sale.client_id != user.id:
        raise HTTPException(status_code=403, detail='Insufficient permissions')
    return get_notification_provider().send(event="sale.updated", sale_id=sale.id, channel=channel)


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
    return commerce_service.checkout(db, user.id, data)


@router.get('/sales', response_model=list[SaleResponse])
def sales_history(
    client_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role not in PRIVILEGED:
        return commerce_service.list_sales(db, user.id)
    return commerce_service.list_sales(db, client_id)


@router.get('/sales/{sale_id}', response_model=SaleResponse)
def get_sale(sale_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sale = commerce_service.get_sale(db, sale_id)
    if user.role not in PRIVILEGED and sale.client_id != user.id:
        raise HTTPException(status_code=403, detail='Insufficient permissions')
    return sale


@router.get('/sales/{sale_id}/receipt', response_model=ReceiptResponse)
def sale_receipt(sale_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sale = commerce_service.get_sale(db, sale_id)
    if user.role not in PRIVILEGED and sale.client_id != user.id:
        raise HTTPException(status_code=403, detail='Insufficient permissions')
    return commerce_service.get_receipt(db, sale_id)


@router.post('/sales/pos', response_model=SaleResponse, status_code=201, dependencies=[staff])
def register_pos_sale(
    data: PosSaleCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return commerce_service.pos_sale(db, user.id, data)


@router.get('/reservations', response_model=list[ReservationResponse])
def list_reservations(
    status: ReservationStatus | None = None,
    branch_id: int | None = None,
    reservation_date: DateType | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role not in RESERVATION_STAFF:
        return commerce_service.list_reservations(db, user.id, status.value if status else None, branch_id, reservation_date)
    return commerce_service.list_reservations(db, None, status.value if status else None, branch_id, reservation_date)


@router.post('/reservations', response_model=ReservationResponse, status_code=201)
def create_reservation(
    data: ReservationCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return commerce_service.create_reservation(db, user.id, data)


@router.get('/reservations/{reservation_id}', response_model=ReservationResponse)
def get_reservation(
    reservation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    reservation = commerce_service.get_reservation(db, reservation_id)
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
    if user.role not in RESERVATION_STAFF and reservation.client_id != user.id:
        raise HTTPException(status_code=403, detail='Insufficient permissions')
    commerce_service.delete_reservation(db, reservation_id)