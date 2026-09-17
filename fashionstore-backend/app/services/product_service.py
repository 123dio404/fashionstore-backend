from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.product import Category, Color, Product, ProductVariant, Size
from app.schemas.product import ProductCreate, ProductUpdate

def _require(model, db: Session, object_id, label: str):
    obj = db.get(model, object_id)
    if obj is None: raise HTTPException(status_code=404, detail=f'{label} not found')
    return obj

def create_product(db: Session, data: ProductCreate) -> Product:
    _require(Category, db, data.category_id, 'Category')
    if db.scalar(select(Product).where(Product.name == data.name)): raise HTTPException(409, 'Product already exists')
    product = Product(**data.model_dump(exclude={'variants'}))
    for item in data.variants:
        _require(Size, db, item.size_id, 'Size'); _require(Color, db, item.color_id, 'Color')
        product.variants.append(ProductVariant(**item.model_dump()))
    db.add(product)
    try: db.commit(); db.refresh(product)
    except IntegrityError:
        db.rollback(); raise HTTPException(409, 'Product or variant already exists')
    return product

def update_product(db: Session, product: Product, data: ProductUpdate) -> Product:
    values = data.model_dump(exclude_unset=True)
    if values.get('category_id') is not None: _require(Category, db, values['category_id'], 'Category')
    if values.get('name') and values['name'] != product.name and db.scalar(select(Product).where(Product.name == values['name'])):
        raise HTTPException(409, 'Product already exists')
    for key, value in values.items(): setattr(product, key, value)
    try: db.commit(); db.refresh(product)
    except IntegrityError:
        db.rollback(); raise HTTPException(409, 'Product already exists')
    return product