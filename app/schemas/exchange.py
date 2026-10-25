from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field
from app.schemas.common import ORMModel


class ExchangeCreateRequest(BaseModel):
    original_sale_id: int = Field(description="ID de la venta original donde se compró la prenda")
    returned_stock_id: int = Field(description="ID de inventario de la prenda que devuelve el cliente")
    new_stock_id: int = Field(description="ID de inventario de la nueva prenda que desea llevarse")
    quantity: int = Field(default=1, ge=1, description="Cantidad de prendas a cambiar")
    reason: str = Field(default="Cambio de talla / modelo", description="Motivo del cambio")


class ExchangeResponse(ORMModel):
    id: int
    original_sale_id: int
    branch_id: int
    tenant_id: int | None = None
    returned_stock_id: int
    new_stock_id: int
    quantity: int
    price_difference: Decimal
    reason: str
    created_at: datetime
    receipt_number: str | None = None
