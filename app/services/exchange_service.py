from datetime import datetime, timezone
from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.commerce import Sale, SaleItem
from app.models.exchange import GarmentExchange
from app.models.inventory import Stock, InventoryMovement, MovementType
from app.schemas.exchange import ExchangeCreateRequest, ExchangeResponse


def process_garment_exchange(
    db: Session,
    cashier_id: int,
    data: ExchangeCreateRequest,
    current_tenant_id: int | None = None,
) -> ExchangeResponse:
    """
    Procesa un cambio de prenda de vestir validando:
    1. Existencia y pertenencia de la venta original al tenant.
    2. Antigüedad máxima de 30 días calendario (RN-06).
    3. Que la prenda devuelta forme parte de la venta original.
    4. Disponibilidad de stock de la nueva prenda.
    5. Actualización atómica de inventario y cálculo de diferencia de precio.
    """
    sale = db.get(Sale, data.original_sale_id)
    if not sale:
        raise HTTPException(status_code=404, detail="Venta original no encontrada")

    if current_tenant_id is not None and sale.tenant_id is not None and sale.tenant_id != current_tenant_id:
        raise HTTPException(status_code=403, detail="La venta original no pertenece a su empresa")

    now = datetime.now(timezone.utc)
    sale_date = sale.sale_date
    if sale_date.tzinfo is None:
        sale_date = sale_date.replace(tzinfo=timezone.utc)

    days_elapsed = (now - sale_date).days
    if days_elapsed > 30:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"El plazo máximo para cambios de prendas (30 días) ha expirado. "
                f"Esta compra fue realizada hace {days_elapsed} días."
            ),
        )

    # Validar que la prenda devuelta estaba en la venta original
    orig_item = next((item for item in sale.items if item.stock_id == data.returned_stock_id), None)
    if not orig_item:
        raise HTTPException(
            status_code=400,
            detail="La prenda devuelta no figura en los detalles de la venta original presentada",
        )

    if orig_item.quantity < data.quantity:
        raise HTTPException(
            status_code=400,
            detail=f"La cantidad a devolver ({data.quantity}) excede la cantidad comprada ({orig_item.quantity})",
        )

    returned_stock = db.get(Stock, data.returned_stock_id)
    new_stock = db.get(Stock, data.new_stock_id)
    if not returned_stock or not new_stock:
        raise HTTPException(status_code=404, detail="Uno de los registros de inventario no existe")

    # Validar disponibilidad de la nueva prenda
    available = new_stock.physical_stock - new_stock.reserved_stock
    if available < data.quantity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No hay stock suficiente de la nueva prenda solicitada (Disponibles: {available}, Requeridos: {data.quantity})",
        )

    # Precios
    returned_price = orig_item.unit_price
    new_price = new_stock.variant.price if new_stock.variant else Decimal("0.00")
    price_diff = (new_price - returned_price) * Decimal(data.quantity)

    # Ajuste de inventario atómico
    returned_stock.physical_stock += data.quantity
    new_stock.physical_stock -= data.quantity

    db.add(
        InventoryMovement(
            movement_type=MovementType.INGRESO,
            inventory_id=returned_stock.id,
            quantity=data.quantity,
            reason=f"Reingreso por cambio de prenda (Venta original #{sale.id})",
        )
    )
    db.add(
        InventoryMovement(
            movement_type=MovementType.VENTA,
            inventory_id=new_stock.id,
            quantity=-data.quantity,
            reason=f"Egreso por cambio de prenda (Venta original #{sale.id})",
        )
    )

    exchange = GarmentExchange(
        tenant_id=sale.tenant_id,
        branch_id=new_stock.branch_id,
        original_sale_id=sale.id,
        returned_stock_id=returned_stock.id,
        new_stock_id=new_stock.id,
        quantity=data.quantity,
        price_difference=price_diff,
        reason=data.reason,
        user_id=cashier_id,
        created_at=now,
    )
    db.add(exchange)
    db.commit()
    db.refresh(exchange)

    return ExchangeResponse(
        id=exchange.id,
        original_sale_id=exchange.original_sale_id,
        branch_id=exchange.branch_id,
        tenant_id=exchange.tenant_id,
        returned_stock_id=exchange.returned_stock_id,
        new_stock_id=exchange.new_stock_id,
        quantity=exchange.quantity,
        price_difference=exchange.price_difference,
        reason=exchange.reason,
        created_at=exchange.created_at,
        receipt_number=f"CHG-{exchange.id:08d}",
    )
