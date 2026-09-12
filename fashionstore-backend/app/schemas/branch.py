from pydantic import BaseModel, Field
from app.schemas.common import ORMModel

class CityCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
class CityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
class CityResponse(ORMModel):
    id: int
    name: str

class BranchCreate(BaseModel):
    city_id: int
    name: str = Field(min_length=2, max_length=150)
    address: str = Field(min_length=2, max_length=255)
    is_active: bool = True
class BranchUpdate(BaseModel):
    city_id: int | None = None
    name: str | None = Field(default=None, min_length=2, max_length=150)
    address: str | None = Field(default=None, min_length=2, max_length=255)
    is_active: bool | None = None
class BranchResponse(ORMModel):
    id: int
    city_id: int
    name: str
    address: str
    is_active: bool