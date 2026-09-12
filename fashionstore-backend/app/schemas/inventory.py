from datetime import datetime
from pydantic import BaseModel, Field
from app.models.inventory import MovementType
from app.schemas.common import ORMModel
class StockResponse(ORMModel):
    id: int; branch_id: int; variant_id: int; size_id: int | None; physical_stock: int; reserved_stock: int
    available_stock: int = 0
    @classmethod
    def from_orm(cls, obj):
        data = super().from_orm(obj); data.available_stock = obj.physical_stock - obj.reserved_stock; return data
class StockAdjustment(BaseModel):
    branch_id: int; variant_id: int; quantity: int = Field(ne=0); reason: str | None = None
class MovementCreate(BaseModel):
    movement_type: MovementType = MovementType.TRANSFERENCIA
    variant_id: int
    source_branch_id: int | None = None
    destination_branch_id: int | None = None
    quantity: int = Field(gt=0)
    reason: str | None = None
class TransferRequest(BaseModel):
    variant_id: int; source_branch_id: int; destination_branch_id: int
    quantity: int = Field(gt=0); reason: str | None = None
class MovementResponse(ORMModel):
    id: int; movement_type: MovementType; inventory_id: int; variant_id: int
    quantity: int; reason: str | None; created_at: datetime
class AvailabilityResponse(BaseModel):
    product_id: int; variant_id: int; branch_id: int; physical_stock: int
    reserved_stock: int; available_stock: int