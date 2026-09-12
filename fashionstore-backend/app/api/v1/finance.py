from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.models.finance import FeeType
from app.models.user import Role, User
from app.schemas.finance import (
    FeeCreate,
    FeeResponse,
    FeeUpdate,
    FinancialReportResponse,
    FineCreate,
    FineResponse,
    FineUpdate,
    PaymentCreate,
    PaymentResponse,
)
from app.services import finance_service

router = APIRouter(prefix='/finance', tags=['finance'])
editor = Depends(require_role(Role.ADMINISTRADOR, Role.ENCARGADO))

PRIVILEGED = (Role.ADMINISTRADOR, Role.ENCARGADO)


@router.get('/fees', response_model=list[FeeResponse])
def list_fees(
    fee_type: FeeType | None = None,
    period: str | None = Query(default=None, pattern=r'^\d{4}-\d{2}$'),
    db: Session = Depends(get_db),
):
    return finance_service.list_fees(db, fee_type, period)


@router.post('/fees', response_model=FeeResponse, status_code=201, dependencies=[editor])
def create_fee(data: FeeCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return finance_service.create_fee(db, data, user.id)


@router.get('/fees/{fee_id}', response_model=FeeResponse)
def get_fee(fee_id: UUID, db: Session = Depends(get_db)):
    return finance_service.get_fee(db, fee_id)


@router.patch('/fees/{fee_id}', response_model=FeeResponse, dependencies=[editor])
def update_fee(fee_id: UUID, data: FeeUpdate, db: Session = Depends(get_db)):
    return finance_service.update_fee(db, fee_id, data)


@router.delete('/fees/{fee_id}', status_code=204, dependencies=[editor])
def delete_fee(fee_id: UUID, db: Session = Depends(get_db)):
    finance_service.delete_fee(db, fee_id)


@router.post('/payments', response_model=PaymentResponse, status_code=201)
def pay_fee(data: PaymentCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return finance_service.process_payment(db, data, user.id)


@router.get('/payments', response_model=list[PaymentResponse])
def list_payments(
    fee_id: UUID | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role in PRIVILEGED:
        return finance_service.list_payments(db, fee_id)
    return finance_service.list_payments(db, fee_id, user_id=user.id)


@router.post('/fines', response_model=FineResponse, status_code=201, dependencies=[editor])
def create_fine(data: FineCreate, db: Session = Depends(get_db)):
    return finance_service.create_fine(db, data)


@router.get('/fines', response_model=list[FineResponse])
def list_fines(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role in PRIVILEGED:
        return finance_service.list_fines(db)
    return finance_service.list_fines(db, user_id=user.id)


@router.get('/fines/{fine_id}', response_model=FineResponse)
def get_fine(fine_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    fine = finance_service.get_fine(db, fine_id)
    if user.role not in PRIVILEGED and fine.user_id != user.id:
        raise HTTPException(status_code=403, detail='Insufficient permissions')
    return fine


@router.patch('/fines/{fine_id}', response_model=FineResponse, dependencies=[editor])
def update_fine(fine_id: UUID, data: FineUpdate, db: Session = Depends(get_db)):
    return finance_service.update_fine(db, fine_id, data)


@router.get('/reports/financial', response_model=FinancialReportResponse, dependencies=[editor])
def financial_report(
    period: str = Query(..., pattern=r'^\d{4}-\d{2}$'),
    db: Session = Depends(get_db),
):
    return finance_service.financial_report(db, period)