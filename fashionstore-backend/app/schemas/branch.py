from uuid import UUID
from pydantic import BaseModel, Field
from app.schemas.common import ORMModel

class CityCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    country: str = Field(default='Colombia', min_length=2, max_length=100)
class CityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    country: str | None = Field(default=None, min_length=2, max_length=100)
class CityResponse(ORMModel):
    id: UUID
    name: str
    country: str

class BranchCreate(BaseModel):
    city_id: UUID
    name: str = Field(min_length=2, max_length=150)
    address: str = Field(min_length=2, max_length=255)
    fitting_rooms: int = Field(default=0, ge=0)
    manager_id: UUID | None = None
    is_active: bool = True
class BranchUpdate(BaseModel):
    city_id: UUID | None = None
    name: str | None = Field(default=None, min_length=2, max_length=150)
    address: str | None = Field(default=None, min_length=2, max_length=255)
    fitting_rooms: int | None = Field(default=None, ge=0)
    manager_id: UUID | None = None
    is_active: bool | None = None
class BranchResponse(ORMModel):
    id: UUID
    city_id: UUID
    manager_id: UUID | None
    name: str
    address: str
    fitting_rooms: int
    is_active: bool
