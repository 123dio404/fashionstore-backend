from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.deps import get_current_user, get_db, require_role
from app.models.commerce import Sale
from app.models.user import Role, User
from app.schemas.commerce import SaleResponse
from app.schemas.sync import SyncBatchRequest, SyncBatchResponse
from app.services.sync_service import process_sync_batch
from app.services import commerce_service

router = APIRouter(prefix="/sync", tags=["sync"])
staff = Depends(require_role(Role.ADMINISTRADOR, Role.ENCARGADO, Role.CAJERO, Role.SUPERADMIN))


@router.post("/batch", response_model=SyncBatchResponse, dependencies=[staff])
def sync_batch(
    data: SyncBatchRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Sincroniza un lote de operaciones registradas sin conexión (PWA o Móvil).
    Garantiza idempotencia (RNF05) mediante UUID y gestiona conflictos de stock (RN-05).
    """
    return process_sync_batch(db=db, user=user, data=data)


@router.get("/conflicts", response_model=list[SaleResponse], dependencies=[staff])
def list_conflicts(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lista las ventas registradas offline que entraron en CONFLICTO por falta de stock central.
    Permite al administrador auditar y gestionar las compensaciones necesarias.
    """
    query = select(Sale).where(Sale.sync_status == "CONFLICTO").order_by(Sale.sale_date.desc())
    if user.tenant_id is not None:
        query = query.where(Sale.tenant_id == user.tenant_id)
    conflicted_sales = db.scalars(query).all()
    return [commerce_service.sale_response(db, s) for s in conflicted_sales]


@router.post("/conflicts/{sale_id}/resolve", response_model=SaleResponse, dependencies=[staff])
def resolve_conflict(
    sale_id: int,
    action: str = "compensar_administrativo",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Marca un conflicto de sobreventa offline como resuelto administrativamente.
    """
    sale = db.get(Sale, sale_id)
    if not sale:
        raise HTTPException(status_code=404, detail="Venta en conflicto no encontrada")
    if user.tenant_id is not None and sale.tenant_id != user.tenant_id:
        raise HTTPException(status_code=403, detail="La venta pertenece a otra empresa")

    sale.sync_status = "RESUELTO_ADMIN"
    db.commit()
    db.refresh(sale)
    return commerce_service.sale_response(db, sale)
