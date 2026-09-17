from uuid import UUID
from pydantic import BaseModel, Field
from app.schemas.common import ORMModel
class SupplierCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    tax_id: str = Field(min_length=2, max_length=50)
    contact_name: str | None = None; email: str | None = None; phone: str | None = None
    address: str | None = None; notes: str | None = None
class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    tax_id: str | None = Field(default=None, min_length=2, max_length=50)
    contact_name: str | None = None; email: str | None = None; phone: str | None = None
    address: str | None = None; notes: str | None = None
class SupplierResponse(ORMModel):
    id: UUID; name: str; tax_id: str; contact_name: str | None; email: str | None
    phone: str | None; address: str | None; notes: str | None
