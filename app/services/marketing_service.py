from datetime import date
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.marketing import Collection, Promotion
from app.models.product import Product
from app.schemas.marketing import CollectionCreate, PromotionCreate


def _products(db, product_ids):
    products = list(db.scalars(select(Product).where(Product.id.in_(product_ids))).all()) if product_ids else []
    if len(products) != len(set(product_ids or [])):
        raise HTTPException(404, "One or more products not found")
    return products


def collection(db: Session, collection_id: int):
    obj = db.scalar(select(Collection).options(selectinload(Collection.products)).where(Collection.id == collection_id))
    if not obj:
        raise HTTPException(404, "Collection not found")
    return obj


def list_collections(db: Session, active_only=False):
    query = select(Collection).options(selectinload(Collection.products)).order_by(Collection.id)
    if active_only:
        query = query.where(Collection.is_active.is_(True))
    return list(db.scalars(query).all())


def create_collection(db: Session, data: CollectionCreate, product_ids=None):
    values = data.model_dump(exclude={"product_ids"})
    obj = Collection(**values, products=_products(db, product_ids if product_ids is not None else data.product_ids))
    db.add(obj); db.commit(); db.refresh(obj)
    return collection(db, obj.id)


def update_collection(db: Session, obj: Collection, data: CollectionCreate, product_ids=None):
    for key, value in data.model_dump(exclude={"product_ids"}).items(): setattr(obj, key, value)
    obj.products = _products(db, product_ids if product_ids is not None else data.product_ids)
    db.commit(); return collection(db, obj.id)


def delete_collection(db: Session, obj: Collection):
    db.delete(obj); db.commit()


def promotion(db: Session, promotion_id: int):
    obj = db.scalar(select(Promotion).options(selectinload(Promotion.products)).where(Promotion.id == promotion_id))
    if not obj: raise HTTPException(404, "Promotion not found")
    return obj


def list_promotions(db: Session, active_only=False):
    today = date.today()
    query = select(Promotion).options(selectinload(Promotion.products)).order_by(Promotion.id)
    if active_only:
        query = query.where(Promotion.is_active.is_(True), (Promotion.start_date.is_(None) | (Promotion.start_date <= today)), (Promotion.end_date.is_(None) | (Promotion.end_date >= today)))
    return list(db.scalars(query).all())


def create_promotion(db: Session, data: PromotionCreate, product_ids=None):
    values = data.model_dump(exclude={"product_ids"})
    obj = Promotion(**values, products=_products(db, product_ids if product_ids is not None else data.product_ids))
    db.add(obj); db.commit(); db.refresh(obj)
    return promotion(db, obj.id)


def update_promotion(db: Session, obj: Promotion, data: PromotionCreate, product_ids=None):
    for key, value in data.model_dump(exclude={"product_ids"}).items(): setattr(obj, key, value)
    obj.products = _products(db, product_ids if product_ids is not None else data.product_ids)
    db.commit(); return promotion(db, obj.id)


def delete_promotion(db: Session, obj: Promotion):
    db.delete(obj); db.commit()
