from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.finance import FeeType, FineStatus, PaymentMethod
from app.schemas.common import ORMModel


class FeeCreate(BaseModel):
    fee_type: FeeType
    period: str = Field(pattern=r"^\d{4}-\d{2}$", description="Periodo en formato YYYY-MM")
    concept: str = Field(min_length=1, max_length=200)
    amount: float = Field(gt=0)
    due_date: datetime | None = None
    description: str | None = None


class FeeUpdate(BaseModel):
    fee_type: FeeType | None = None
    period: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    concept: str | None = Field(default=None, min_length=1, max_length=200)
    amount: float | None = Field(default=None, gt=0)
    due_date: datetime | None = None
    description: str | None = None


class FeeResponse(ORMModel):
    id: UUID
    fee_type: FeeType
    period: str
    concept: str
    amount: float
    due_date: datetime | None
    description: str | None
    created_by_id: UUID
    created_at: datetime


class PaymentCreate(BaseModel):
    fee_id: UUID
    amount: float = Field(gt=0)
    method: PaymentMethod = PaymentMethod.TARJETA


class PaymentResponse(ORMModel):
    id: UUID
    fee_id: UUID
    user_id: UUID
    amount: float
    method: PaymentMethod
    status: str
    reference: str | None
    paid_at: datetime | None
    created_at: datetime


class FineCreate(BaseModel):
    user_id: UUID
    fee_id: UUID | None = None
    reason: str = Field(min_length=1, max_length=255)
    amount: float = Field(gt=0)


class FineUpdate(BaseModel):
    reason: str | None = Field(default=None, min_length=1, max_length=255)
    amount: float | None = Field(default=None, gt=0)
    status: FineStatus | None = None


class FineResponse(ORMModel):
    id: UUID
    user_id: UUID
    fee_id: UUID | None
    reason: str
    amount: float
    status: FineStatus
    issued_at: datetime
    paid_at: datetime | None
    created_at: datetime


class FeeLedgerItem(BaseModel):
    id: UUID
    fee_type: FeeType
    period: str
    concept: str
    amount: Decimal
    due_date: datetime | None
    collected: Decimal
    pending: Decimal


class FinancialSummary(BaseModel):
    period: str
    total_fees: int = 0
    total_amount: float = 0.0
    total_collected: float = 0.0
    total_pending: float = 0.0
    fine_total: float = 0.0
    collection_rate: float = 0.0


class FinancialReportResponse(BaseModel):
    summary: FinancialSummary
    fees: list[FeeLedgerItem]
    fines: list[FineResponse]