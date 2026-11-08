from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_optional_current_user, require_role
from app.models.tenant import Tenant
from app.models.user import Role, User
from app.schemas.marketing import CollectionCreate, CollectionResponse, PromotionCreate, PromotionResponse
from app.services import marketing_service as service

router = APIRouter(tags=["collections-promotions"])
admin_user = Depends(require_role(Role.ADMINISTRADOR))


@router.get("/collections", response_model=list[CollectionResponse])
def collections(
    active_only: bool = Query(False),
    tenant_id: int | None = None,
    current: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    target_tenant = current.tenant_id if current and current.role != Role.SUPERADMIN else tenant_id
    if target_tenant is None and current is None:
        target_tenant = db.scalar(select(Tenant.id).where(Tenant.status == "Activo").order_by(Tenant.id))
    return service.list_collections(db, active_only, tenant_id=target_tenant)


@router.post("/collections", response_model=CollectionResponse, status_code=201)
def create_collection(
    data: CollectionCreate,
    current: User = admin_user,
    db: Session = Depends(get_db),
):
    return service.create_collection(db, data, tenant_id=current.tenant_id)


@router.put("/collections/{collection_id}", response_model=CollectionResponse)
def update_collection(
    collection_id: int,
    data: CollectionCreate,
    current: User = admin_user,
    db: Session = Depends(get_db),
):
    col = service.collection(db, collection_id)
    if current.role != Role.SUPERADMIN and current.tenant_id is not None and col.tenant_id != current.tenant_id:
        raise HTTPException(404, "Collection not found")
    return service.update_collection(db, col, data)


@router.delete("/collections/{collection_id}", status_code=204)
def delete_collection(
    collection_id: int,
    current: User = admin_user,
    db: Session = Depends(get_db),
):
    col = service.collection(db, collection_id)
    if current.role != Role.SUPERADMIN and current.tenant_id is not None and col.tenant_id != current.tenant_id:
        raise HTTPException(404, "Collection not found")
    service.delete_collection(db, col)


@router.get("/promotions", response_model=list[PromotionResponse])
def promotions(
    active_only: bool = Query(False),
    tenant_id: int | None = None,
    current: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    target_tenant = current.tenant_id if current and current.role != Role.SUPERADMIN else tenant_id
    if target_tenant is None and current is None:
        target_tenant = db.scalar(select(Tenant.id).where(Tenant.status == "Activo").order_by(Tenant.id))
    return service.list_promotions(db, active_only, tenant_id=target_tenant)


@router.post("/promotions", response_model=PromotionResponse, status_code=201)
def create_promotion(
    data: PromotionCreate,
    current: User = admin_user,
    db: Session = Depends(get_db),
):
    return service.create_promotion(db, data, tenant_id=current.tenant_id)


@router.put("/promotions/{promotion_id}", response_model=PromotionResponse)
def update_promotion(
    promotion_id: int,
    data: PromotionCreate,
    current: User = admin_user,
    db: Session = Depends(get_db),
):
    promo = service.promotion(db, promotion_id)
    if current.role != Role.SUPERADMIN and current.tenant_id is not None and promo.tenant_id != current.tenant_id:
        raise HTTPException(404, "Promotion not found")
    return service.update_promotion(db, promo, data)


@router.delete("/promotions/{promotion_id}", status_code=204)
def delete_promotion(
    promotion_id: int,
    current: User = admin_user,
    db: Session = Depends(get_db),
):
    promo = service.promotion(db, promotion_id)
    if current.role != Role.SUPERADMIN and current.tenant_id is not None and promo.tenant_id != current.tenant_id:
        raise HTTPException(404, "Promotion not found")
    service.delete_promotion(db, promo)
