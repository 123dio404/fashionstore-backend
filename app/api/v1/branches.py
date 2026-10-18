from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db, require_role, get_current_tenant_id
from app.models.branch import Branch, City
from app.models.tenant import Subscription, Tenant
from app.models.user import Role, User
from app.schemas.branch import BranchCreate, BranchResponse, BranchUpdate, CityCreate, CityResponse, CityUpdate

router = APIRouter(tags=['branches'])
manager = Depends(require_role(Role.ADMINISTRADOR, Role.ENCARGADO, Role.SUPERADMIN))

@router.get('/cities', response_model=list[CityResponse])
def cities(db: Session = Depends(get_db)):
    return list(db.scalars(select(City).order_by(City.name)).all())

@router.post('/cities', response_model=CityResponse, status_code=201, dependencies=[manager])
def add_city(data: CityCreate, db: Session = Depends(get_db)):
    obj = City(**data.model_dump())
    db.add(obj)
    try:
        db.commit()
        db.refresh(obj)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'City already exists')
    return obj

@router.get('/cities/{city_id}', response_model=CityResponse)
def get_city(city_id: int, db: Session = Depends(get_db)):
    obj = db.get(City, city_id)
    if not obj:
        raise HTTPException(404, 'City not found')
    return obj

@router.patch('/cities/{city_id}', response_model=CityResponse, dependencies=[manager])
def edit_city(city_id: int, data: CityUpdate, db: Session = Depends(get_db)):
    obj = db.get(City, city_id)
    if not obj:
        raise HTTPException(404, 'City not found')
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    try:
        db.commit()
        db.refresh(obj)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'City already exists')
    return obj

@router.delete('/cities/{city_id}', status_code=204, dependencies=[manager])
def delete_city(city_id: int, db: Session = Depends(get_db)):
    obj = db.get(City, city_id)
    if not obj:
        raise HTTPException(404, 'City not found')
    try:
        db.delete(obj)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'City has branches')

@router.get('/branches', response_model=list[BranchResponse])
def branches(
    tenant_id: int | None = None,
    db: Session = Depends(get_db),
):
    """Lista sucursales. Si se especifica tenant_id filtra por la empresa correspondiente."""
    query = select(Branch).order_by(Branch.name)
    if tenant_id:
        query = query.where(Branch.tenant_id == tenant_id)
    return list(db.scalars(query).all())

@router.post('/branches', response_model=BranchResponse, status_code=201)
def add_branch(
    data: BranchCreate,
    user: User = Depends(require_role(Role.ADMINISTRADOR, Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    """Crea una nueva sucursal validando estrictamente los límites del plan contratado (RN-02)."""
    if not db.get(City, data.city_id):
        raise HTTPException(404, 'City not found')

    tenant_id = user.tenant_id
    if tenant_id:
        sub = db.scalar(
            select(Subscription).where(Subscription.tenant_id == tenant_id, Subscription.status == "Activa")
        )
        if sub and sub.plan:
            active_count = db.scalar(
                select(func.count(Branch.id)).where(Branch.tenant_id == tenant_id, Branch.is_active == True)
            ) or 0
            if active_count >= sub.plan.max_branches:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        f"Límite alcanzado: Su Plan {sub.plan.name} solo permite un máximo de {sub.plan.max_branches} "
                        f"sucursales activas. Actualice al Plan Profesional para habilitar hasta 10 sucursales."
                    ),
                )
    obj = Branch(**data.model_dump(), tenant_id=tenant_id)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.get('/branches/{branch_id}', response_model=BranchResponse)
def get_branch(branch_id: int, db: Session = Depends(get_db)):
    obj = db.get(Branch, branch_id)
    if not obj:
        raise HTTPException(404, 'Branch not found')
    return obj

@router.patch('/branches/{branch_id}', response_model=BranchResponse, dependencies=[manager])
def edit_branch(branch_id: int, data: BranchUpdate, db: Session = Depends(get_db)):
    obj = db.get(Branch, branch_id)
    if not obj:
        raise HTTPException(404, 'Branch not found')
    vals = data.model_dump(exclude_unset=True)
    if 'city_id' in vals and not db.get(City, vals['city_id']):
        raise HTTPException(404, 'City not found')
    for k, v in vals.items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj

@router.delete('/branches/{branch_id}', status_code=204, dependencies=[manager])
def delete_branch(branch_id: int, db: Session = Depends(get_db)):
    obj = db.get(Branch, branch_id)
    if not obj:
        raise HTTPException(404, 'Branch not found')
    db.delete(obj)
    db.commit()

