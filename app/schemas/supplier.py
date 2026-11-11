from decimal import Decimal
from pydantic import BaseModel, Field
from app.schemas.common import ORMModel
class SupplierCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    ci: str = Field(min_length=2, max_length=30)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=150)
    address: str | None = Field(default=None, max_length=255)
    is_active: bool = True
class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    ci: str | None = Field(default=None, min_length=2, max_length=30)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=150)
    address: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None
class SupplierResponse(ORMModel):
    id: int; name: str; ci: str; phone: str | None; email: str | None
    address: str | None; is_active: bool


class PurchaseItem(BaseModel):
    variant_id: int = Field(description="ID de variante de prenda a ingresar")
    quantity: int = Field(ge=1, description="Cantidad física adquirida")
    cost_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2, description="Costo unitario de compra al proveedor")


class PurchaseOrderCreate(BaseModel):
    branch_id: int = Field(description="ID de sucursal física donde ingresa la mercadería")
    invoice_number: str = Field(description="Número de factura o nota de entrega del proveedor")
    items: list[PurchaseItem] = Field(min_length=1, description="Lote de prendas compradas")


class PurchaseOrderResponse(BaseModel):
    supplier_id: int
    supplier_name: str
    branch_id: int
    invoice_number: str
    total_cost: Decimal
    items_count: int
    message: str
