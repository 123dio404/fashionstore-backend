from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.models.user import Role, User
from app.schemas.reporting import (
    AnalyticalQueryRequest, AnalyticalQueryResponse, DashboardResponse,
    InventoryReportResponse, PurchaseHistoryResponse, SalesReportResponse,
)
from app.services import reporting_service as service

router = APIRouter(prefix="/reports", tags=["reports"])
sales_report_access = Depends(require_role(Role.ADMINISTRADOR, Role.ENCARGADO))
admin_report_access = Depends(require_role(Role.ADMINISTRADOR))


@router.get("/purchases/history", response_model=PurchaseHistoryResponse)
def purchase_history(
    client_id: int | None = Query(None, ge=1),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = client_id or user.id
    if client_id and client_id != user.id and user.role not in {Role.ADMINISTRADOR, Role.ENCARGADO}:
        raise HTTPException(403, "Insufficient permissions")
    return service.purchase_history(db, target, start_date, end_date)


@router.get("/sales", response_model=SalesReportResponse, dependencies=[sales_report_access])
def sales_report(start_date: datetime | None = None, end_date: datetime | None = None, db: Session = Depends(get_db)):
    return service.sales_report(db, start_date, end_date)


@router.get("/inventory", response_model=InventoryReportResponse, dependencies=[admin_report_access])
def inventory_report(db: Session = Depends(get_db)):
    return service.inventory_report(db)


@router.get("/executive", response_model=DashboardResponse, dependencies=[admin_report_access])
def executive_dashboard(start_date: datetime | None = None, end_date: datetime | None = None, db: Session = Depends(get_db)):
    return service.dashboard(db, start_date, end_date)


@router.post("/analytical-query", response_model=AnalyticalQueryResponse, dependencies=[admin_report_access])
def analytical_query(data: AnalyticalQueryRequest, db: Session = Depends(get_db)):
    return service.analytical_query(db, data.query, data.client_id, data.start_date, data.end_date, data.audio)
