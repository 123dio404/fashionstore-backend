from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from app.api.deps import get_db, require_role
from app.models.inventory import Stock
from app.models.product import Category, Color, Product, ProductVariant, Season, Size
from app.models.supplier import Supplier
from app.models.user import Role
from app.schemas.inventory import AvailabilityResponse
from app.schemas.product import (CategoryResponse, ColorResponse, ParameterCreate, ParameterUpdate, ProductCreate, ProductResponse, ProductUpdate, SeasonResponse, SizeResponse, VariantCreate, VariantResponse)
from app.services.product_service import create_product, update_product
router = APIRouter(tags=['products'])
editor = Depends(require_role(Role.ADMINISTRADOR, Role.ENCARGADO))

@router.get('/parameters/categories', response_model=list[CategoryResponse])
def list_categories(db: Session = Depends(get_db)): return list(db.scalars(select(Category).order_by(Category.name)).all())
@router.post('/parameters/categories', response_model=CategoryResponse, status_code=201, dependencies=[editor])
def add_category(data: ParameterCreate, db: Session = Depends(get_db)):
    obj=Category(name=data.name,description=data.description); db.add(obj)
    try: db.commit(); db.refresh(obj)
    except IntegrityError: db.rollback(); raise HTTPException(409,'Category already exists')
    return obj
@router.patch('/parameters/categories/{item_id}', response_model=CategoryResponse, dependencies=[editor])
def edit_category(item_id: UUID, data: ParameterUpdate, db: Session = Depends(get_db)):
    obj=db.get(Category,item_id)
    if not obj: raise HTTPException(404,'Category not found')
    for k,v in data.model_dump(exclude_unset=True).items():
        if k in {'name','description'}: setattr(obj,k,v)
    db.commit(); db.refresh(obj); return obj

@router.get('/parameters/seasons', response_model=list[SeasonResponse])
def list_seasons(db: Session = Depends(get_db)): return list(db.scalars(select(Season).order_by(Season.name)).all())
@router.post('/parameters/seasons', response_model=SeasonResponse, status_code=201, dependencies=[editor])
def add_season(data: ParameterCreate, db: Session = Depends(get_db)):
    obj=Season(name=data.name); db.add(obj)
    try: db.commit(); db.refresh(obj)
    except IntegrityError: db.rollback(); raise HTTPException(409,'Season already exists')
    return obj


@router.delete('/parameters/categories/{item_id}', status_code=204, dependencies=[editor])
def delete_category(item_id: UUID, db: Session = Depends(get_db)):
    obj = db.get(Category, item_id)
    if not obj:
        raise HTTPException(404, 'Category not found')
    try:
        db.delete(obj)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Category is in use')
@router.patch('/parameters/seasons/{item_id}', response_model=SeasonResponse, dependencies=[editor])
def edit_season(item_id: UUID, data: ParameterUpdate, db: Session = Depends(get_db)):
    obj=db.get(Season,item_id)
    if not obj: raise HTTPException(404,'Season not found')
    if data.name is not None: obj.name=data.name
    db.commit(); db.refresh(obj); return obj


@router.delete('/parameters/seasons/{item_id}', status_code=204, dependencies=[editor])
def delete_season(item_id: UUID, db: Session = Depends(get_db)):
    obj = db.get(Season, item_id)
    if not obj:
        raise HTTPException(404, 'Season not found')
    db.delete(obj)
    db.commit()

@router.get('/parameters/sizes', response_model=list[SizeResponse])
def list_sizes(db: Session = Depends(get_db)): return list(db.scalars(select(Size).order_by(Size.name)).all())
@router.post('/parameters/sizes', response_model=SizeResponse, status_code=201, dependencies=[editor])
def add_size(data: ParameterCreate, db: Session = Depends(get_db)):
    obj=Size(name=data.name); db.add(obj)
    try: db.commit(); db.refresh(obj)
    except IntegrityError: db.rollback(); raise HTTPException(409,'Size already exists')
    return obj
@router.patch('/parameters/sizes/{item_id}', response_model=SizeResponse, dependencies=[editor])
def edit_size(item_id: UUID, data: ParameterUpdate, db: Session = Depends(get_db)):
    obj=db.get(Size,item_id)
    if not obj: raise HTTPException(404,'Size not found')
    if data.name is not None: obj.name=data.name
    db.commit(); db.refresh(obj); return obj


@router.delete('/parameters/sizes/{item_id}', status_code=204, dependencies=[editor])
def delete_size(item_id: UUID, db: Session = Depends(get_db)):
    obj = db.get(Size, item_id)
    if not obj:
        raise HTTPException(404, 'Size not found')
    db.delete(obj)
    db.commit()

@router.get('/parameters/colors', response_model=list[ColorResponse])
def list_colors(db: Session = Depends(get_db)): return list(db.scalars(select(Color).order_by(Color.name)).all())
@router.post('/parameters/colors', response_model=ColorResponse, status_code=201, dependencies=[editor])
def add_color(data: ParameterCreate, db: Session = Depends(get_db)):
    if not data.hex_code: raise HTTPException(422,'hex_code is required for colors')
    obj=Color(name=data.name,hex_code=data.hex_code); db.add(obj)
    try: db.commit(); db.refresh(obj)
    except IntegrityError: db.rollback(); raise HTTPException(409,'Color already exists')
    return obj
@router.patch('/parameters/colors/{item_id}', response_model=ColorResponse, dependencies=[editor])
def edit_color(item_id: UUID, data: ParameterUpdate, db: Session = Depends(get_db)):
    obj=db.get(Color,item_id)
    if not obj: raise HTTPException(404,'Color not found')
    if data.name is not None: obj.name=data.name
    if data.hex_code is not None: obj.hex_code=data.hex_code
    db.commit(); db.refresh(obj); return obj


@router.delete('/parameters/colors/{item_id}', status_code=204, dependencies=[editor])
def delete_color(item_id: UUID, db: Session = Depends(get_db)):
    obj = db.get(Color, item_id)
    if not obj:
        raise HTTPException(404, 'Color not found')
    db.delete(obj)
    db.commit()

@router.get('/products', response_model=list[ProductResponse])
def list_products(db: Session = Depends(get_db)):
    return list(db.scalars(select(Product).options(selectinload(Product.variants)).order_by(Product.name)).all())
@router.post('/products', response_model=ProductResponse, status_code=201, dependencies=[editor])
def add_product(data: ProductCreate, db: Session = Depends(get_db)): return create_product(db,data)
@router.get('/products/{product_id}', response_model=ProductResponse)
def get_product(product_id: UUID, db: Session = Depends(get_db)):
    obj=db.scalar(select(Product).where(Product.id==product_id).options(selectinload(Product.variants)))
    if not obj: raise HTTPException(404,'Product not found')
    return obj
@router.patch('/products/{product_id}', response_model=ProductResponse, dependencies=[editor])
def edit_product(product_id: UUID, data: ProductUpdate, db: Session = Depends(get_db)):
    obj=db.get(Product,product_id)
    if not obj: raise HTTPException(404,'Product not found')
    return update_product(db,obj,data)
@router.delete('/products/{product_id}', status_code=204, dependencies=[editor])
def delete_product(product_id: UUID, db: Session = Depends(get_db)):
    obj = db.get(Product, product_id)
    if not obj: raise HTTPException(404, 'Product not found')
    db.delete(obj)
    db.commit()
@router.post('/products/{product_id}/variants', response_model=VariantResponse, status_code=201, dependencies=[editor])
def add_variant(product_id: UUID, data: VariantCreate, db: Session = Depends(get_db)):
    if not db.get(Product,product_id): raise HTTPException(404,'Product not found')
    if not db.get(Size,data.size_id): raise HTTPException(404,'Size not found')
    if not db.get(Color,data.color_id): raise HTTPException(404,'Color not found')
    obj=ProductVariant(product_id=product_id,**data.model_dump()); db.add(obj)
    try: db.commit(); db.refresh(obj)
    except IntegrityError: db.rollback(); raise HTTPException(409,'Variant already exists')
    return obj
@router.get('/products/{product_id}/availability', response_model=list[AvailabilityResponse])
def availability(product_id: UUID, branch_id: UUID, db: Session = Depends(get_db)):
    if not db.get(Product,product_id): raise HTTPException(404,'Product not found')
    rows=db.scalars(
        select(Stock)
        .join(ProductVariant)
        .where(ProductVariant.product_id == product_id, Stock.branch_id == branch_id)
    ).all()
    return [AvailabilityResponse(product_id=product_id,variant_id=x.variant_id,branch_id=x.branch_id,physical_stock=x.physical_stock,reserved_stock=x.reserved_stock,available_stock=x.physical_stock-x.reserved_stock) for x in rows]
