from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field
from app.models.inventory import MovementType
from app.schemas.common import ORMModel
class StockResponse(ORMModel):
    id: UUID; branch_id: UUID; variant_id: UUID; physical_stock: int; reserved_stock: int
    available_stock: int = 0
    @classmethod
    def from_orm(cls, obj):
        data = super().from_orm(obj); data.available_stock = obj.physical_stock - obj.reserved_stock; return data
class StockAdjustment(BaseModel):
    branch_id: UUID; variant_id: UUID; quantity: int = Field(ne=0); reason: str | None = None
class MovementCreate(BaseModel):
    movement_type: MovementType = MovementType.TRANSFERENCIA
    variant_id: UUID
    source_branch_id: UUID | None = None
    destination_branch_id: UUID | None = None
    quantity: int = Field(gt=0)
    reason: str | None = None
class TransferRequest(BaseModel):
    variant_id: UUID; source_branch_id: UUID; destination_branch_id: UUID
    quantity: int = Field(gt=0); reason: str | None = None
class MovementResponse(ORMModel):
    id: UUID; movement_type: MovementType; variant_id: UUID; source_branch_id: UUID | None
    destination_branch_id: UUID | None; quantity: int; reason: str | None; performed_by_id: UUID
    created_at: datetime
class AvailabilityResponse(BaseModel):
    product_id: UUID; variant_id: UUID; branch_id: UUID; physical_stock: int
    reserved_stock: int; available_stock: int
