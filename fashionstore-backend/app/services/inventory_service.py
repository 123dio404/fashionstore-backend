from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.branch import Branch
from app.models.inventory import InventoryMovement, MovementType, Stock
from app.models.product import ProductVariant
from app.schemas.inventory import StockAdjustment, TransferRequest

def _stock(db: Session, branch_id, variant_id, lock: bool = True) -> Stock:
    q = select(Stock).where(Stock.branch_id == branch_id, Stock.variant_id == variant_id)
    if lock: q = q.with_for_update()
    stock = db.scalar(q)
    if stock is None:
        variant = db.get(ProductVariant, variant_id)
        stock = Stock(branch_id=branch_id, variant_id=variant_id, size_id=variant.size_id, physical_stock=0, reserved_stock=0)
        db.add(stock); db.flush()
    return stock

def _movement(db: Session, movement_type: MovementType, stock: Stock, quantity: int, reason: str | None, ) -> InventoryMovement:
    m = InventoryMovement(movement_type=movement_type, inventory_id=stock.id, quantity=quantity, reason=reason)
    db.add(m)
    return m

def adjust_stock(
    db: Session,
    data: StockAdjustment,
    user_id,
    movement_type: MovementType = MovementType.AJUSTE,
) -> Stock:
    try:
        if db.get(Branch, data.branch_id) is None:
            raise HTTPException(404, 'Branch not found')
        if db.get(ProductVariant, data.variant_id) is None:
            raise HTTPException(404, 'Product variant not found')
        stock = _stock(db, data.branch_id, data.variant_id)
        if stock.physical_stock + data.quantity < 0 or stock.physical_stock + data.quantity < stock.reserved_stock:
            raise HTTPException(400, 'Insufficient stock')
        stock.physical_stock += data.quantity
        _movement(db, movement_type, stock, data.quantity, data.reason)
        db.commit(); db.refresh(stock); return stock
    except HTTPException:
        db.rollback()
        raise

def transfer_stock(db: Session, data: TransferRequest, user_id) -> InventoryMovement:
    if data.source_branch_id == data.destination_branch_id: raise HTTPException(400, 'Source and destination branches must differ')
    try:
        if db.get(Branch, data.source_branch_id) is None or db.get(Branch, data.destination_branch_id) is None:
            raise HTTPException(404, 'Source or destination branch not found')
        if db.get(ProductVariant, data.variant_id) is None:
            raise HTTPException(404, 'Product variant not found')
        source = _stock(db, data.source_branch_id, data.variant_id); destination = _stock(db, data.destination_branch_id, data.variant_id)
        if source.physical_stock - source.reserved_stock < data.quantity: raise HTTPException(400, 'Insufficient available stock')
        source.physical_stock -= data.quantity; destination.physical_stock += data.quantity
        _movement(db, MovementType.TRANSFERENCIA, source, -data.quantity, f'Transferencia salida: {data.reason or ""}')
        movement = _movement(db, MovementType.TRANSFERENCIA, destination, data.quantity, f'Transferencia entrada: {data.reason or ""}')
        db.commit(); db.refresh(movement)
        return movement
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        raise