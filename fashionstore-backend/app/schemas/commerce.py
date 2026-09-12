import enum
from datetime import date as DateType, datetime, time
from decimal import Decimal
from uuid import UUID

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
    EN_TIENDA = "en_tienda"
    COMPLETADA = "completada"
    CANCELADA = "cancelada"


class CartItemRequest(BaseModel):
    stock_id: UUID
    quantity: int = Field(gt=0)


class CartItemUpdate(BaseModel):
    quantity: int = Field(gt=0)


class CartItemResponse(BaseModel):
    id: UUID
    stock_id: UUID
    quantity: int
    price: Decimal
    variant_id: UUID
    product_id: UUID
    product_name: str
    size: str | None = None
    color: str | None = None


class CartResponse(BaseModel):
    id: UUID
    status: CartStatus
    items: list[CartItemResponse]
    total: Decimal


class CheckoutRequest(BaseModel):
    branch_id: UUID


class SaleItemInput(BaseModel):
    stock_id: UUID
    quantity: int = Field(gt=0)


class PosSaleCreate(BaseModel):
    branch_id: UUID
    client_id: UUID | None = None
    items: list[SaleItemInput] = Field(min_length=1)
    paid: bool = True


class SaleItemResponse(ORMModel):
    id: UUID
    stock_id: UUID
    quantity: int
    unit_price: Decimal


class SalePaymentResponse(ORMModel):
    id: UUID
    sale_id: UUID
    amount: Decimal
    status: PaymentStatus
    paid_at: datetime | None
    reference: str | None


class SaleResponse(ORMModel):
    id: UUID
    client_id: UUID | None
    user_id: UUID
    branch_id: UUID
    sale_date: datetime
    total: Decimal
    sale_type: SaleType
    items: list[SaleItemResponse] = []
    payments: list[SalePaymentResponse] = []


class ReservationItemInput(BaseModel):
    stock_id: UUID
    quantity: int = Field(gt=0)


class ReservationCreate(BaseModel):
    branch_id: UUID
    reservation_date: DateType
    reservation_time: time
    items: list[ReservationItemInput] = Field(min_length=1)


class ReservationUpdate(BaseModel):
    reservation_date: DateType | None = None
    reservation_time: time | None = None
    status: ReservationStatus | None = None


class ReservationItemResponse(ORMModel):
    id: UUID
    stock_id: UUID
    quantity: int


class ReservationResponse(ORMModel):
    id: UUID
    client_id: UUID
    branch_id: UUID
    reservation_date: DateType
    reservation_time: time
    status: ReservationStatus
    items: list[ReservationItemResponse] = []