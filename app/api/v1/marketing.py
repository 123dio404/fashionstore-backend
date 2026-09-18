from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.models.user import Role, User
from app.schemas.marketing import CollectionCreate, CollectionResponse, PromotionCreate, PromotionResponse
from app.services import marketing_service as service

router = APIRouter(tags=["collections-promotions"])
admin = Depends(require_role(Role.ADMINISTRADOR))


@router.get("/collections", response_model=list[CollectionResponse])
def collections(active_only: bool = Query(False), db: Session = Depends(get_db)):
    return service.list_collections(db, active_only)


@router.post("/collections", response_model=CollectionResponse, status_code=201, dependencies=[admin])
def create_collection(data: CollectionCreate, db: Session = Depends(get_db)):
    return service.create_collection(db, data)


@router.put("/collections/{collection_id}", response_model=CollectionResponse, dependencies=[admin])
def update_collection(collection_id: int, data: CollectionCreate, db: Session = Depends(get_db)):
    return service.update_collection(db, service.collection(db, collection_id), data)


@router.delete("/collections/{collection_id}", status_code=204, dependencies=[admin])
def delete_collection(collection_id: int, db: Session = Depends(get_db)):
    service.delete_collection(db, service.collection(db, collection_id))


@router.get("/promotions", response_model=list[PromotionResponse])
def promotions(active_only: bool = Query(False), db: Session = Depends(get_db)):
    return service.list_promotions(db, active_only)


@router.post("/promotions", response_model=PromotionResponse, status_code=201, dependencies=[admin])
def create_promotion(data: PromotionCreate, db: Session = Depends(get_db)):
    return service.create_promotion(db, data)


@router.put("/promotions/{promotion_id}", response_model=PromotionResponse, dependencies=[admin])
def update_promotion(promotion_id: int, data: PromotionCreate, db: Session = Depends(get_db)):
    return service.update_promotion(db, service.promotion(db, promotion_id), data)


@router.delete("/promotions/{promotion_id}", status_code=204, dependencies=[admin])
def delete_promotion(promotion_id: int, db: Session = Depends(get_db)):
    service.delete_promotion(db, service.promotion(db, promotion_id))
