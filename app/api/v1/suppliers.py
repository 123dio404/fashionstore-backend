from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import get_db, require_role
from app.models.inventory import InventoryMovement, MovementType, Stock
from app.models.product import ProductVariant
from app.models.supplier import ProductSupplier, Supplier
from app.models.user import Role
from app.schemas.supplier import (
    PurchaseOrderCreate,
    PurchaseOrderResponse,
    SupplierCreate,
    SupplierResponse,
    SupplierUpdate,
)
router=APIRouter(prefix='/suppliers',tags=['suppliers'])
editor=Depends(require_role(Role.ADMINISTRADOR,Role.ENCARGADO))
@router.get('',response_model=list[SupplierResponse])
def list_suppliers(db:Session=Depends(get_db)): return list(db.scalars(select(Supplier).order_by(Supplier.name)).all())
@router.post('',response_model=SupplierResponse,status_code=201,dependencies=[editor])
def add_supplier(data:SupplierCreate,db:Session=Depends(get_db)):
    obj=Supplier(**data.model_dump()); db.add(obj)
    try: db.commit(); db.refresh(obj)
    except IntegrityError: db.rollback(); raise HTTPException(409,'CI already exists')
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
    except IntegrityError: db.rollback(); raise HTTPException(409,'CI already exists')
    return obj
@router.delete('/{supplier_id}',status_code=204,dependencies=[editor])
def delete_supplier(supplier_id: int,db:Session=Depends(get_db)):
    obj=db.get(Supplier,supplier_id)
    if not obj: raise HTTPException(404,'Supplier not found')
    db.delete(obj); db.commit()


@router.post('/{supplier_id}/purchases', response_model=PurchaseOrderResponse, status_code=201, dependencies=[editor])
def create_purchase_order(
    supplier_id: int,
    data: PurchaseOrderCreate,
    db: Session = Depends(get_db),
):
    """
    Registra una compra formal a proveedor (Nota de Ingreso de mercadería textil).
    Alimenta el inventario físico con trazabilidad de compras y costos (RN audio).
    """
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(404, "Proveedor no encontrado")

    total_cost = Decimal("0.00")
    total_items = 0

    for item in data.items:
        variant = db.get(ProductVariant, item.variant_id)
        if not variant:
            raise HTTPException(404, f"Variante de producto #{item.variant_id} no encontrada")

        stock = db.scalar(
            select(Stock).where(Stock.branch_id == data.branch_id, Stock.variant_id == item.variant_id)
        )
        if not stock:
            stock = Stock(
                branch_id=data.branch_id,
                variant_id=item.variant_id,
                size_id=variant.size_id,
                physical_stock=0,
                reserved_stock=0,
                min_stock=5,
            )
            db.add(stock)
            db.flush()

        stock.physical_stock += item.quantity
        db.add(
            InventoryMovement(
                movement_type=MovementType.INGRESO,
                inventory_id=stock.id,
                quantity=item.quantity,
                reason=f"Ingreso por compra a proveedor '{supplier.name}' - Factura #{data.invoice_number}",
            )
        )

        prod_sup = db.get(ProductSupplier, (variant.product_id, supplier.id))
        if prod_sup:
            prod_sup.purchase_price = item.cost_price
        else:
            db.add(ProductSupplier(product_id=variant.product_id, supplier_id=supplier.id, purchase_price=item.cost_price))

        total_cost += item.cost_price * item.quantity
        total_items += item.quantity

    db.commit()

    return PurchaseOrderResponse(
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        branch_id=data.branch_id,
        invoice_number=data.invoice_number,
        total_cost=total_cost,
        items_count=total_items,
        message=f"Se ingresaron {total_items} prendas al inventario de la sucursal #{data.branch_id} con éxito.",
    )
