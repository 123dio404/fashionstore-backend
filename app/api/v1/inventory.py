from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db, require_role
from app.models.inventory import InventoryMovement, MovementType, Stock
from app.models.user import Role, User
from app.schemas.inventory import MovementCreate, MovementResponse, StockAdjustment, StockResponse, TransferRequest
from app.services.inventory_service import adjust_stock, transfer_stock
router=APIRouter(prefix='/inventory',tags=['inventory'])
operator=Depends(require_role(Role.ADMINISTRADOR,Role.ENCARGADO))

def stock_response(stock: Stock) -> StockResponse:
    return StockResponse(id=stock.id,branch_id=stock.branch_id,variant_id=stock.variant_id,size_id=stock.size_id,physical_stock=stock.physical_stock,reserved_stock=stock.reserved_stock,available_stock=stock.physical_stock-stock.reserved_stock)

@router.get('/stock',response_model=list[StockResponse])
def list_stock(branch_id: int|None=None, variant_id: int|None=None, db:Session=Depends(get_db)):
    query=select(Stock).order_by(Stock.updated_at)
    if branch_id: query=query.where(Stock.branch_id==branch_id)
    if variant_id: query=query.where(Stock.variant_id==variant_id)
    return [stock_response(x) for x in db.scalars(query).all()]
@router.get('/stock/{stock_id}',response_model=StockResponse)
def get_stock(stock_id: int,db:Session=Depends(get_db)):
    obj=db.get(Stock,stock_id)
    if not obj: raise HTTPException(404,'Stock not found')
    return stock_response(obj)
@router.post('/movements/adjustment',response_model=StockResponse,dependencies=[operator])
def adjustment(data:StockAdjustment,db:Session=Depends(get_db),current:User=Depends(get_current_user)):
    return stock_response(adjust_stock(db,data,current.id))
@router.post('/movements',response_model=MovementResponse|StockResponse,status_code=201,dependencies=[operator])
def create_movement(data: MovementCreate, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    if data.movement_type.value == 'transferencia':
        if data.source_branch_id is None or data.destination_branch_id is None:
            raise HTTPException(422, 'Both source and destination branches are required for transfers')
        return transfer_stock(db, TransferRequest(**data.model_dump()), current.id)
    branch_id = data.destination_branch_id or data.source_branch_id
    if branch_id is None:
        raise HTTPException(422, 'A branch is required for stock movements')
    adjustment_data = StockAdjustment(branch_id=branch_id, variant_id=data.variant_id, quantity=data.quantity, reason=data.reason)
    movement_type = (
        MovementType.INGRESO
        if data.movement_type == MovementType.INGRESO
        else MovementType.AJUSTE
    )
    stock = adjust_stock(db, adjustment_data, current.id, movement_type)
    if data.movement_type.value == 'ingreso':
        return stock
    return stock
@router.post('/transfers',response_model=MovementResponse,status_code=201,dependencies=[operator])
def transfer(data:TransferRequest,db:Session=Depends(get_db),current:User=Depends(get_current_user)):
    return transfer_stock(db,data,current.id)
@router.post('/movements/transfer',response_model=MovementResponse,status_code=201,include_in_schema=False,dependencies=[operator])
def transfer_alias(data:TransferRequest,db:Session=Depends(get_db),current:User=Depends(get_current_user)):
    return transfer_stock(db,data,current.id)
@router.get('/movements',response_model=list[MovementResponse])
def movements(variant_id: int|None=None, branch_id: int|None=None, db:Session=Depends(get_db)):
    query = select(InventoryMovement).join(Stock, Stock.id == InventoryMovement.inventory_id).order_by(InventoryMovement.created_at.desc())
    if variant_id: query = query.where(Stock.variant_id == variant_id)
    if branch_id: query = query.where(Stock.branch_id == branch_id)
    return list(db.scalars(query).all())
