import re
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field, field_validator
from app.schemas.common import ORMModel

class ParameterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    hex_code: str | None = None
class ParameterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    hex_code: str | None = None
class CategoryResponse(ORMModel):
    id: UUID; name: str; description: str | None = None
class SeasonResponse(ORMModel):
    id: UUID; name: str
class SizeResponse(ORMModel):
    id: UUID; name: str
class ColorResponse(ORMModel):
    id: UUID; name: str; hex_code: str

class VariantCreate(BaseModel):
    size_id: UUID
    color_id: UUID
    barcode: str | None = Field(default=None, max_length=80)
class VariantResponse(ORMModel):
    id: UUID
    product_id: UUID
    size_id: UUID
    color_id: UUID
    barcode: str | None

class ProductCreate(BaseModel):
    category_id: UUID
    season_id: UUID | None = None
    supplier_id: UUID | None = None
    name: str = Field(min_length=2, max_length=150)
    sku: str = Field(min_length=1, max_length=50)
    description: str | None = None
    technical_metadata: str | None = None
    model_3d_url: str | None = Field(default=None, max_length=500)
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    is_active: bool = True
    variants: list[VariantCreate] = Field(default_factory=list)

    @field_validator('model_3d_url')
    @classmethod
    def validate_model_url(cls, value: str | None) -> str | None:
        if value is None: return value
        if not re.match(r'^https?://', value, re.I) or not value.lower().split('?', 1)[0].endswith(('.glb', '.gltf')):
            raise ValueError('model_3d_url must be an HTTP(S) URL ending in .glb or .gltf')
        return value

class ProductUpdate(BaseModel):
    category_id: UUID | None = None
    season_id: UUID | None = None
    supplier_id: UUID | None = None
    name: str | None = Field(default=None, min_length=2, max_length=150)
    sku: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = None
    technical_metadata: str | None = None
    model_3d_url: str | None = Field(default=None, max_length=500)
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    is_active: bool | None = None

    @field_validator('model_3d_url')
    @classmethod
    def validate_model_url(cls, value: str | None) -> str | None:
        if value is not None and (not re.match(r'^https?://', value, re.I) or not value.lower().split('?', 1)[0].endswith(('.glb', '.gltf'))):
            raise ValueError('model_3d_url must be an HTTP(S) URL ending in .glb or .gltf')
        return value

class ProductResponse(ORMModel):
    id: UUID; category_id: UUID; season_id: UUID | None; supplier_id: UUID | None
    name: str; sku: str; description: str | None; technical_metadata: str | None
    model_3d_url: str | None; price: Decimal; is_active: bool
    variants: list[VariantResponse] = []
