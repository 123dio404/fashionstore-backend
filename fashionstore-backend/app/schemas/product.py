from decimal import Decimal
from pydantic import BaseModel, Field
from app.schemas.common import ORMModel

class ParameterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
class ParameterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
class CategoryResponse(ORMModel):
    id: int; name: str
class SeasonResponse(ORMModel):
    id: int; name: str
class SizeResponse(ORMModel):
    id: int; name: str
class ColorResponse(ORMModel):
    id: int; name: str

class VariantCreate(BaseModel):
    size_id: int
    color_id: int
    codigo: str = Field(min_length=1, max_length=50)
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
class VariantResponse(ORMModel):
    id: int
    product_id: int
    size_id: int | None
    color_id: int | None
    codigo: str
    price: Decimal | None
    is_active: bool

class ProductCreate(BaseModel):
    category_id: int
    name: str = Field(min_length=2, max_length=150)
    brand: str | None = Field(default=None, max_length=100)
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    is_active: bool = True
    variants: list[VariantCreate] = Field(default_factory=list)

class ProductUpdate(BaseModel):
    category_id: int | None = None
    name: str | None = Field(default=None, min_length=2, max_length=150)
    brand: str | None = Field(default=None, max_length=100)
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    is_active: bool | None = None

class ProductResponse(ORMModel):
    id: int; category_id: int
    name: str; brand: str | None; price: Decimal; is_active: bool
    variants: list[VariantResponse] = []