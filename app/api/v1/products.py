from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from app.api.deps import get_db, require_role, get_optional_current_user
from app.models.inventory import Stock
from app.models.product import Category, Color, Product, ProductVariant, Season, Size
from app.models.tenant import Tenant
from app.models.user import Role, User
from app.schemas.inventory import AvailabilityResponse
from app.schemas.product import (CategoryResponse, ColorResponse, ParameterCreate, ParameterUpdate, ProductCreate, ProductResponse, ProductUpdate, SeasonResponse, SizeResponse, VariantCreate, VariantResponse, VariantUpdate)
from app.services.product_service import create_product, update_product
router = APIRouter(tags=['products'])
editor = Depends(require_role(Role.ADMINISTRADOR, Role.ENCARGADO))

@router.get('/parameters/categories', response_model=list[CategoryResponse])
def list_categories(
    tenant_id: int | None = None,
    current: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Lista categorías disponibles. Si el usuario pertenece a una empresa, filtra por su tenant."""
    query = select(Category).order_by(Category.name)
    target_tenant = None
    if current is not None and current.role != Role.SUPERADMIN and current.tenant_id is not None:
        target_tenant = current.tenant_id
    elif tenant_id is not None:
        target_tenant = tenant_id

    if target_tenant is not None:
        query = query.where(Category.tenant_id == target_tenant)
    return list(db.scalars(query).all())


@router.post('/parameters/categories', response_model=CategoryResponse, status_code=201)
def add_category(
    data: ParameterCreate,
    current: User = Depends(require_role(Role.ADMINISTRADOR, Role.ENCARGADO)),
    db: Session = Depends(get_db),
):
    obj = Category(name=data.name, tenant_id=current.tenant_id)
    db.add(obj)
    try:
        db.commit()
        db.refresh(obj)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Category already exists')
    return obj


@router.patch('/parameters/categories/{item_id}', response_model=CategoryResponse)
def edit_category(
    item_id: int,
    data: ParameterUpdate,
    current: User = Depends(require_role(Role.ADMINISTRADOR, Role.ENCARGADO)),
    db: Session = Depends(get_db),
):
    obj = db.get(Category, item_id)
    if not obj:
        raise HTTPException(404, 'Category not found')
    if current.role != Role.SUPERADMIN and current.tenant_id is not None and obj.tenant_id != current.tenant_id:
        raise HTTPException(403, 'No autorizado para modificar esta categoría')
    for k, v in data.model_dump(exclude_unset=True).items():
        if k == 'name':
            setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete('/parameters/categories/{item_id}', status_code=204)
def delete_category(
    item_id: int,
    current: User = Depends(require_role(Role.ADMINISTRADOR, Role.ENCARGADO)),
    db: Session = Depends(get_db),
):
    obj = db.get(Category, item_id)
    if not obj:
        raise HTTPException(404, 'Category not found')
    if current.role != Role.SUPERADMIN and current.tenant_id is not None and obj.tenant_id != current.tenant_id:
        raise HTTPException(403, 'No autorizado para eliminar esta categoría')
    try:
        db.delete(obj)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Category is in use')

@router.get('/parameters/seasons', response_model=list[SeasonResponse])
def list_seasons(db: Session = Depends(get_db)): return list(db.scalars(select(Season).order_by(Season.name)).all())
@router.post('/parameters/seasons', response_model=SeasonResponse, status_code=201, dependencies=[editor])
def add_season(data: ParameterCreate, db: Session = Depends(get_db)):
    if data.start_date and data.end_date and data.end_date < data.start_date:
        raise HTTPException(422, 'Season end date must be after start date')
    obj=Season(name=data.name, start_date=data.start_date, end_date=data.end_date); db.add(obj)
    try: db.commit(); db.refresh(obj)
    except IntegrityError: db.rollback(); raise HTTPException(409,'Season already exists')
    return obj



@router.patch('/parameters/seasons/{item_id}', response_model=SeasonResponse, dependencies=[editor])
def edit_season(item_id: int, data: ParameterUpdate, db: Session = Depends(get_db)):
    obj=db.get(Season,item_id)
    if not obj: raise HTTPException(404,'Season not found')
    values = data.model_dump(exclude_unset=True)
    if values.get('start_date') and values.get('end_date') and values['end_date'] < values['start_date']:
        raise HTTPException(422, 'Season end date must be after start date')
    for key, value in values.items(): setattr(obj, key, value)
    db.commit(); db.refresh(obj); return obj


@router.delete('/parameters/seasons/{item_id}', status_code=204, dependencies=[editor])
def delete_season(item_id: int, db: Session = Depends(get_db)):
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
def edit_size(item_id: int, data: ParameterUpdate, db: Session = Depends(get_db)):
    obj=db.get(Size,item_id)
    if not obj: raise HTTPException(404,'Size not found')
    if data.name is not None: obj.name=data.name
    db.commit(); db.refresh(obj); return obj


@router.delete('/parameters/sizes/{item_id}', status_code=204, dependencies=[editor])
def delete_size(item_id: int, db: Session = Depends(get_db)):
    obj = db.get(Size, item_id)
    if not obj:
        raise HTTPException(404, 'Size not found')
    db.delete(obj)
    db.commit()

@router.get('/parameters/colors', response_model=list[ColorResponse])
def list_colors(db: Session = Depends(get_db)): return list(db.scalars(select(Color).order_by(Color.name)).all())
@router.post('/parameters/colors', response_model=ColorResponse, status_code=201, dependencies=[editor])
def add_color(data: ParameterCreate, db: Session = Depends(get_db)):
    obj=Color(name=data.name); db.add(obj)
    try: db.commit(); db.refresh(obj)
    except IntegrityError: db.rollback(); raise HTTPException(409,'Color already exists')
    return obj
@router.patch('/parameters/colors/{item_id}', response_model=ColorResponse, dependencies=[editor])
def edit_color(item_id: int, data: ParameterUpdate, db: Session = Depends(get_db)):
    obj=db.get(Color,item_id)
    if not obj: raise HTTPException(404,'Color not found')
    if data.name is not None: obj.name=data.name
    db.commit(); db.refresh(obj); return obj


@router.delete('/parameters/colors/{item_id}', status_code=204, dependencies=[editor])
def delete_color(item_id: int, db: Session = Depends(get_db)):
    obj = db.get(Color, item_id)
    if not obj:
        raise HTTPException(404, 'Color not found')
    db.delete(obj)
    db.commit()

@router.get('/products', response_model=list[ProductResponse])
def list_products(
    tenant_id: int | None = None,
    current: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """Catálogo público. Si hay usuario autenticado se restringe a su empresa (aislamiento multitenant)."""
    query = select(Product).options(selectinload(Product.variants)).order_by(Product.name)
    if current is not None and current.role != Role.SUPERADMIN and current.tenant_id is not None:
        query = query.where(Product.tenant_id == current.tenant_id)
    elif tenant_id is not None:
        query = query.where(Product.tenant_id == tenant_id)
    else:
        # Si no hay usuario autenticado ni parámetro de tenant, aislar a la empresa por defecto (Moda Urbana)
        # para que nunca aparezcan medias o prendas de gala mezcladas en la tienda general.
        default_tenant = db.scalar(select(Tenant.id).where(Tenant.status == "Activo").order_by(Tenant.id))
        if default_tenant:
            query = query.where(Product.tenant_id == default_tenant)
    return list(db.scalars(query).all())


@router.post('/products', response_model=ProductResponse, status_code=201)
def add_product(
    data: ProductCreate,
    current: User = Depends(require_role(Role.ADMINISTRADOR, Role.ENCARGADO)),
    db: Session = Depends(get_db),
):
    return create_product(db, data, tenant_id=current.tenant_id)


@router.get('/products/{product_id}', response_model=ProductResponse)
def get_product(
    product_id: int,
    current: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    return _scoped_product(db, product_id, current)


@router.patch('/products/{product_id}', response_model=ProductResponse)
def edit_product(
    product_id: int,
    data: ProductUpdate,
    current: User = Depends(require_role(Role.ADMINISTRADOR, Role.ENCARGADO)),
    db: Session = Depends(get_db),
):
    obj = _scoped_product(db, product_id, current)
    return update_product(db, obj, data)


@router.delete('/products/{product_id}', status_code=204)
def delete_product(
    product_id: int,
    current: User = Depends(require_role(Role.ADMINISTRADOR, Role.ENCARGADO)),
    db: Session = Depends(get_db),
):
    obj = _scoped_product(db, product_id, current)
    db.delete(obj)
    db.commit()


@router.post('/products/{product_id}/variants', response_model=VariantResponse, status_code=201)
def add_variant(
    product_id: int,
    data: VariantCreate,
    current: User = Depends(require_role(Role.ADMINISTRADOR, Role.ENCARGADO)),
    db: Session = Depends(get_db),
):
    if not _scoped_product(db, product_id, current): raise HTTPException(404,'Product not found')
    if not db.get(Size,data.size_id): raise HTTPException(404,'Size not found')
    if not db.get(Color,data.color_id): raise HTTPException(404,'Color not found')
    obj=ProductVariant(product_id=product_id,**data.model_dump()); db.add(obj)
    try: db.commit(); db.refresh(obj)
    except IntegrityError: db.rollback(); raise HTTPException(409,'Variant already exists')
    return obj


@router.patch('/products/{product_id}/variants/{variant_id}', response_model=VariantResponse)
def edit_variant(
    product_id: int,
    variant_id: int,
    data: VariantUpdate,
    current: User = Depends(require_role(Role.ADMINISTRADOR, Role.ENCARGADO)),
    db: Session = Depends(get_db),
):
    """Edita talla, color, código, precio o estado de una variante (CU-05)."""
    _scoped_product(db, product_id, current)
    variant = db.scalar(select(ProductVariant).where(ProductVariant.id == variant_id, ProductVariant.product_id == product_id))
    if not variant: raise HTTPException(404, 'Variant not found')
    values = data.model_dump(exclude_unset=True)
    if values.get('size_id') is not None and not db.get(Size, values['size_id']): raise HTTPException(404, 'Size not found')
    if values.get('color_id') is not None and not db.get(Color, values['color_id']): raise HTTPException(404, 'Color not found')
    for key, value in values.items(): setattr(variant, key, value)
    try: db.commit(); db.refresh(variant)
    except IntegrityError: db.rollback(); raise HTTPException(409, 'Variant already exists')
    return variant


@router.delete('/products/{product_id}/variants/{variant_id}', status_code=204)
def delete_variant(
    product_id: int,
    variant_id: int,
    current: User = Depends(require_role(Role.ADMINISTRADOR, Role.ENCARGADO)),
    db: Session = Depends(get_db),
):
    _scoped_product(db, product_id, current)
    variant = db.scalar(select(ProductVariant).where(ProductVariant.id == variant_id, ProductVariant.product_id == product_id))
    if not variant: raise HTTPException(404, 'Variant not found')
    try:
        db.delete(variant)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Variant has inventory or sales')


@router.get('/products/{product_id}/availability', response_model=list[AvailabilityResponse])
def availability(product_id: int, branch_id: int, db: Session = Depends(get_db)):
    if not db.get(Product,product_id): raise HTTPException(404,'Product not found')
    rows=db.scalars(
        select(Stock)
        .join(ProductVariant)
        .where(ProductVariant.product_id == product_id, Stock.branch_id == branch_id)
    ).all()
    return [AvailabilityResponse(product_id=product_id,variant_id=x.variant_id,branch_id=x.branch_id,physical_stock=x.physical_stock,reserved_stock=x.reserved_stock,available_stock=x.physical_stock-x.reserved_stock,stock_id=x.id) for x in rows]


def _scoped_product(db: Session, product_id: int, current: User | None) -> Product:
    """Obtiene un producto validando el tenant del usuario (evita acceso cruzado entre empresas)."""
    obj = db.scalar(
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.variants))
    )
    if obj is None:
        raise HTTPException(404, 'Product not found')
    if current is not None and current.tenant_id is not None and obj.tenant_id != current.tenant_id:
        raise HTTPException(404, 'Product not found')
    return obj
