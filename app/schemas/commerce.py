import enum
from datetime import date as DateType, datetime, time
from decimal import Decimal
from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class CartStatus(str, enum.Enum):
    ACTIVO = "activo"
    COMPLETADO = "completado"
    ANULADO = "anulado"


class SaleType(str, enum.Enum):
    DIGITAL = "digital"
    POS = "pos"


class PaymentStatus(str, enum.Enum):
    PENDIENTE = "pendiente"
    COMPLETADO = "completado"
    FALLIDO = "fallido"
    REEMBOLSADO = "reembolsado"


class ReservationStatus(str, enum.Enum):
    PENDIENTE = "pendiente"
    CONFIRMADA = "confirmada"
    PREPARACION = "preparacion"
    LISTA = "lista"
    ASIGNADA = "asignada"
    EN_PROBADOR = "en_probador"
    CHECKOUT = "checkout"
    EN_TIENDA = "en_tienda"
    COMPLETADA = "completada"
    CANCELADA = "cancelada"
    REEMBOLSADA = "reembolsada"
    DEVUELTA = "devuelta"


class CartItemRequest(BaseModel):
    stock_id: int
    quantity: int = Field(gt=0)


class CartItemUpdate(BaseModel):
    quantity: int = Field(gt=0)


class CartItemResponse(BaseModel):
    id: int
    stock_id: int
    quantity: int
    price: Decimal
    variant_id: int
    product_id: int
    product_name: str
    size: str | None = None
    color: str | None = None


class CartResponse(BaseModel):
    id: int
    status: CartStatus
    items: list[CartItemResponse]
    total: Decimal


class CheckoutRequest(BaseModel):
    branch_id: int
    payment_provider: str = "stripe"
    payment_status: PaymentStatus = PaymentStatus.PENDIENTE
    payment_reference: str | None = None
    idempotency_key: str | None = None


class SaleItemInput(BaseModel):
    stock_id: int
    quantity: int = Field(gt=0)


class PosSaleCreate(BaseModel):
    branch_id: int
    client_id: int
    items: list[SaleItemInput] = Field(min_length=1)
    paid: bool = True
    payment_provider: str = "stripe"
    payment_status: PaymentStatus | None = None
    payment_reference: str | None = None


class SaleItemResponse(ORMModel):
    id: int
    stock_id: int
    quantity: int
    unit_price: Decimal


class SalePaymentResponse(ORMModel):
    id: int
    sale_id: int
    amount: Decimal
    status: PaymentStatus
    paid_at: datetime | None
    reference: str | None


class SaleResponse(ORMModel):
    id: int
    client_id: int
    user_id: int | None
    branch_id: int
    sale_date: datetime
    total: Decimal
    sale_type: SaleType
    items: list[SaleItemResponse] = []
    payments: list[SalePaymentResponse] = []


class ReceiptResponse(BaseModel):
    sale_id: int
    receipt_number: str
    invoice_number: str
    sale_date: datetime
    sale_type: SaleType
    branch_id: int
    client_id: int
    subtotal: Decimal
    total: Decimal
    payment_status: PaymentStatus
    items: list[SaleItemResponse]


class ReservationItemInput(BaseModel):
    stock_id: int
    quantity: int = Field(gt=0)


class ReservationCreate(BaseModel):
    branch_id: int
    reservation_date: DateType
    reservation_time: time
    items: list[ReservationItemInput] = Field(min_length=1)


class ReservationUpdate(BaseModel):
    reservation_date: DateType | None = None
    reservation_time: time | None = None
    status: ReservationStatus | None = None
    fitting_room: int | None = Field(default=None, ge=1)


class ReservationItemResponse(ORMModel):
    id: int
    stock_id: int
    quantity: int


class ReservationResponse(ORMModel):
    id: int
    client_id: int
    branch_id: int
    reservation_date: DateType
    reservation_time: time
    status: ReservationStatus
    fitting_room: int | None = None
    prepared_at: datetime | None = None
    assigned_at: datetime | None = None
    checked_out_at: datetime | None = None
    refunded_at: datetime | None = None
    items: list[ReservationItemResponse] = []