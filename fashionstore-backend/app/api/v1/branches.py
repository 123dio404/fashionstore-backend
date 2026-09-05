from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db, require_role
from app.models.branch import Branch, City
from app.models.user import Role, User
from app.schemas.branch import BranchCreate, BranchResponse, BranchUpdate, CityCreate, CityResponse, CityUpdate
router = APIRouter(tags=['branches'])
manager = Depends(require_role(Role.ADMINISTRADOR, Role.ENCARGADO))

@router.get('/cities', response_model=list[CityResponse])
def cities(db: Session = Depends(get_db)): return list(db.scalars(select(City).order_by(City.name)).all())
@router.post('/cities', response_model=CityResponse, status_code=201, dependencies=[manager])
def add_city(data: CityCreate, db: Session = Depends(get_db)):
    obj=City(**data.model_dump()); db.add(obj)
    try: db.commit(); db.refresh(obj)
    except IntegrityError: db.rollback(); raise HTTPException(409, 'City already exists')
    return obj
@router.get('/cities/{city_id}', response_model=CityResponse)
def get_city(city_id: UUID, db: Session = Depends(get_db)):
    obj = db.get(City, city_id)
    if not obj: raise HTTPException(404, 'City not found')
    return obj
@router.patch('/cities/{city_id}', response_model=CityResponse, dependencies=[manager])
def edit_city(city_id: UUID, data: CityUpdate, db: Session = Depends(get_db)):
    obj=db.get(City,city_id)
    if not obj: raise HTTPException(404,'City not found')
    for k,v in data.model_dump(exclude_unset=True).items(): setattr(obj,k,v)
    try: db.commit(); db.refresh(obj)
    except IntegrityError: db.rollback(); raise HTTPException(409,'City already exists')
    return obj
@router.delete('/cities/{city_id}', status_code=204, dependencies=[manager])
def delete_city(city_id: UUID, db: Session = Depends(get_db)):
    obj=db.get(City,city_id)
    if not obj: raise HTTPException(404,'City not found')
    try: db.delete(obj); db.commit()
    except IntegrityError: db.rollback(); raise HTTPException(409,'City has branches')

@router.get('/branches', response_model=list[BranchResponse])
def branches(db: Session = Depends(get_db)): return list(db.scalars(select(Branch).order_by(Branch.name)).all())
@router.post('/branches', response_model=BranchResponse, status_code=201, dependencies=[manager])
def add_branch(data: BranchCreate, db: Session = Depends(get_db)):
    if not db.get(City,data.city_id): raise HTTPException(404,'City not found')
    if data.manager_id and not db.get(User,data.manager_id): raise HTTPException(404,'Manager not found')
    obj=Branch(**data.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj
@router.get('/branches/{branch_id}', response_model=BranchResponse)
def get_branch(branch_id: UUID, db: Session = Depends(get_db)):
    obj=db.get(Branch,branch_id)
    if not obj: raise HTTPException(404,'Branch not found')
    return obj
@router.patch('/branches/{branch_id}', response_model=BranchResponse, dependencies=[manager])
def edit_branch(branch_id: UUID, data: BranchUpdate, db: Session = Depends(get_db)):
    obj=db.get(Branch,branch_id)
    if not obj: raise HTTPException(404,'Branch not found')
    vals=data.model_dump(exclude_unset=True)
    if 'city_id' in vals and not db.get(City,vals['city_id']): raise HTTPException(404,'City not found')
    if 'manager_id' in vals and vals['manager_id'] and not db.get(User,vals['manager_id']): raise HTTPException(404,'Manager not found')
    for k,v in vals.items(): setattr(obj,k,v)
    db.commit(); db.refresh(obj); return obj
@router.delete('/branches/{branch_id}', status_code=204, dependencies=[manager])
def delete_branch(branch_id: UUID, db: Session = Depends(get_db)):
    obj=db.get(Branch,branch_id)
    if not obj: raise HTTPException(404,'Branch not found')
    db.delete(obj); db.commit()
