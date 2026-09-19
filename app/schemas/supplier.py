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
