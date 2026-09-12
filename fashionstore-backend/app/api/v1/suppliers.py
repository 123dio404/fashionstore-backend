from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import get_db, require_role
from app.models.supplier import Supplier
from app.models.user import Role
from app.schemas.supplier import SupplierCreate, SupplierResponse, SupplierUpdate
router=APIRouter(prefix='/suppliers',tags=['suppliers'])
editor=Depends(require_role(Role.ADMINISTRADOR,Role.ENCARGADO))
@router.get('',response_model=list[SupplierResponse])
def list_suppliers(db:Session=Depends(get_db)): return list(db.scalars(select(Supplier).order_by(Supplier.name)).all())
@router.post('',response_model=SupplierResponse,status_code=201,dependencies=[editor])
def add_supplier(data:SupplierCreate,db:Session=Depends(get_db)):
    obj=Supplier(**data.model_dump()); db.add(obj)
    try: db.commit(); db.refresh(obj)
    except IntegrityError: db.rollback(); raise HTTPException(409,'Tax ID already exists')
    return obj
@router.get('/{supplier_id}',response_model=SupplierResponse)
def get_supplier(supplier_id: int,db:Session=Depends(get_db)):
    obj=db.get(Supplier,supplier_id)
    if not obj: raise HTTPException(404,'Supplier not found')
    return obj
@router.patch('/{supplier_id}',response_model=SupplierResponse,dependencies=[editor])
def edit_supplier(supplier_id: int,data:SupplierUpdate,db:Session=Depends(get_db)):
    obj=db.get(Supplier,supplier_id)
    if not obj: raise HTTPException(404,'Supplier not found')
    for k,v in data.model_dump(exclude_unset=True).items(): setattr(obj,k,v)
    try: db.commit(); db.refresh(obj)
    except IntegrityError: db.rollback(); raise HTTPException(409,'Tax ID already exists')
    return obj
@router.delete('/{supplier_id}',status_code=204,dependencies=[editor])
def delete_supplier(supplier_id: int,db:Session=Depends(get_db)):
    obj=db.get(Supplier,supplier_id)
    if not obj: raise HTTPException(404,'Supplier not found')
    db.delete(obj); db.commit()
