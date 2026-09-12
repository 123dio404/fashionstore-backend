from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.finance import (
    Fee,
    FeeType,
    Fine,
    FineStatus,
    Payment,
    PaymentStatus,
)
from app.models.user import User
from app.schemas.finance import (
    FeeCreate,
    FeeLedgerItem,
    FeeUpdate,
    FinancialReportResponse,
    FinancialSummary,
    FineCreate,
    FineUpdate,
    PaymentCreate,
)


def get_fee(db: Session, fee_id: UUID) -> Fee:
    fee = db.get(Fee, fee_id)
    if fee is None:
        raise HTTPException(404, "Fee not found")
    return fee


def list_fees(db: Session, fee_type: FeeType | None = None, period: str | None = None) -> list[Fee]:
    q = select(Fee).order_by(Fee.period.desc(), Fee.created_at.desc())
    if fee_type is not None:
        q = q.where(Fee.fee_type == fee_type)
    if period is not None:
        q = q.where(Fee.period == period)
    return list(db.scalars(q).all())


def create_fee(db: Session, data: FeeCreate, user_id: UUID) -> Fee:
    fee = Fee(**data.model_dump(), created_by_id=user_id)
    db.add(fee)
    db.commit()
    db.refresh(fee)
    return fee


def update_fee(db: Session, fee_id: UUID, data: FeeUpdate) -> Fee:
    fee = get_fee(db, fee_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(fee, k, v)
    db.commit()
    db.refresh(fee)
    return fee


def delete_fee(db: Session, fee_id: UUID) -> None:
    fee = get_fee(db, fee_id)
    db.delete(fee)
    db.commit()


def process_payment(db: Session, data: PaymentCreate, user_id: UUID) -> Payment:
    fee = get_fee(db, data.fee_id)
    collected = sum(p.amount for p in fee.payments if p.status == PaymentStatus.COMPLETADO)
    pending = float(Decimal(str(fee.amount)) - Decimal(str(collected)))
    if data.amount > pending:
        raise HTTPException(400, "Paid amount exceeds pending balance")
    payment = Payment(
        fee_id=data.fee_id,
        user_id=user_id,
        amount=data.amount,
        method=data.method,
        status=PaymentStatus.COMPLETADO,
    )
    db.add(payment)
    db.flush()
    payment.reference = f"PAY-{payment.id.hex[:12].upper()}"
    payment.paid_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(payment)
    return payment


def list_payments(db: Session, fee_id: UUID | None = None, user_id: UUID | None = None) -> list[Payment]:
    q = select(Payment).order_by(Payment.created_at.desc(), Payment.id)
    if fee_id is not None:
        q = q.where(Payment.fee_id == fee_id)
    if user_id is not None:
        q = q.where(Payment.user_id == user_id)
    return list(db.scalars(q).all())


def get_fine(db: Session, fine_id: UUID) -> Fine:
    fine = db.get(Fine, fine_id)
    if fine is None:
        raise HTTPException(404, "Fine not found")
    return fine


def create_fine(db: Session, data: FineCreate) -> Fine:
    if db.get(User, data.user_id) is None:
        raise HTTPException(404, "User not found")
    if data.fee_id is not None and db.get(Fee, data.fee_id) is None:
        raise HTTPException(404, "Fee not found")
    fine = Fine(**data.model_dump())
    db.add(fine)
    db.commit()
    db.refresh(fine)
    return fine


def update_fine(db: Session, fine_id: UUID, data: FineUpdate) -> Fine:
    fine = get_fine(db, fine_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(fine, k, v)
    if fine.status == FineStatus.PAGADA and fine.paid_at is None:
        fine.paid_at = datetime.now(timezone.utc)
    if fine.status != FineStatus.PAGADA:
        fine.paid_at = None
    db.commit()
    db.refresh(fine)
    return fine


def list_fines(db: Session, user_id: UUID | None = None) -> list[Fine]:
    q = select(Fine).order_by(Fine.issued_at.desc(), Fine.id)
    if user_id is not None:
        q = q.where(Fine.user_id == user_id)
    return list(db.scalars(q).all())


def _period_bounds(period: str) -> tuple[datetime, datetime]:
    year, month = int(period[:4]), int(period[5:7])
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    end = datetime(year + 1, 1, 1, tzinfo=timezone.utc) if month == 12 else datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return start, end


def financial_report(db: Session, period: str) -> FinancialReportResponse:
    start, end = _period_bounds(period)
    fees = list_fees(db, period=period)
    fines = list(db.scalars(select(Fine).where(Fine.issued_at >= start, Fine.issued_at < end)).all())

    ledger: list[FeeLedgerItem] = []
    total_amount = Decimal("0")
    total_collected = Decimal("0")
    for fee in fees:
        collected = sum((p.amount for p in fee.payments if p.status == PaymentStatus.COMPLETADO), Decimal("0"))
        total_amount += fee.amount
        total_collected += collected
        ledger.append(
            FeeLedgerItem(
                id=fee.id,
                fee_type=fee.fee_type,
                period=fee.period,
                concept=fee.concept,
                amount=fee.amount,
                due_date=fee.due_date,
                collected=collected,
                pending=fee.amount - collected,
            )
        )
    total_amount_f = float(total_amount)
    total_collected_f = float(total_collected)
    fine_total = float(sum(f.amount for f in fines if f.status in (FineStatus.PENDIENTE, FineStatus.PAGADA)))
    summary = FinancialSummary(
        period=period,
        total_fees=len(ledger),
        total_amount=round(total_amount_f, 2),
        total_collected=round(total_collected_f, 2),
        total_pending=round(total_amount_f - total_collected_f, 2),
        fine_total=round(fine_total, 2),
        collection_rate=round(total_collected_f / total_amount_f, 4) if total_amount_f else 0.0,
    )
    return FinancialReportResponse(summary=summary, fees=ledger, fines=fines)