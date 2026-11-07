from decimal import Decimal
from datetime import date
from pydantic import BaseModel, Field
from app.schemas.common import ORMModel

class ParameterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    start_date: date | None = None
    end_date: date | None = None
class ParameterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    start_date: date | None = None
    end_date: date | None = None
class CategoryResponse(ORMModel):
    id: int; name: str
class SeasonResponse(ORMModel):
    id: int; name: str; start_date: date | None; end_date: date | None
class SizeResponse(ORMModel):
    id: int; name: str
class ColorResponse(ORMModel):
    id: int; name: str

class VariantCreate(BaseModel):
    size_id: int
    color_id: int
    codigo: str = Field(min_length=1, max_length=50)
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)

class VariantUpdate(BaseModel):
    size_id: int | None = None
    color_id: int | None = None
    codigo: str | None = Field(default=None, min_length=1, max_length=50)
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    is_active: bool | None = None
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
    season_id: int | None = None
    name: str = Field(min_length=2, max_length=150)
    brand: str | None = Field(default=None, max_length=100)
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2, description="Precio unitario minorista")
    wholesale_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2, description="Precio al por mayor")
    wholesale_min_quantity: int = Field(default=3, ge=2, description="Cantidad mínima para precio mayorista")
    material: str | None = Field(default=None, max_length=100, description="Tipo de tela o material (algodón, lana, lino, etc.)")
    secondary_color: str | None = Field(default=None, max_length=50, description="Color secundario para prendas multicolores")
    is_clearance: bool = Field(default=False, description="Flag de liquidación de fin de temporada")
    discount_percentage: Decimal = Field(default=Decimal("0.00"), ge=0, le=100, description="Porcentaje de descuento por liquidación")
    is_active: bool = True
    model_3d_url: str | None = Field(default=None, max_length=500)
    model_3d_format: str | None = Field(default=None, pattern=r'^(glb|gltf)$')
    technical_metadata: str | None = None
    variants: list[VariantCreate] = Field(default_factory=list)

class ProductUpdate(BaseModel):
    category_id: int | None = None
    season_id: int | None = None
    name: str | None = Field(default=None, min_length=2, max_length=150)
    brand: str | None = Field(default=None, max_length=100)
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    wholesale_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    wholesale_min_quantity: int | None = Field(default=None, ge=2)
    material: str | None = Field(default=None, max_length=100)
    secondary_color: str | None = Field(default=None, max_length=50)
    is_clearance: bool | None = None
    discount_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    is_active: bool | None = None
    model_3d_url: str | None = Field(default=None, max_length=500)
    model_3d_format: str | None = Field(default=None, pattern=r'^(glb|gltf)$')
    technical_metadata: str | None = None

class ClearanceBatchRequest(BaseModel):
    season_id: int | None = Field(default=None, description="ID de temporada a liquidar (ej. temporada de invierno)")
    category_id: int | None = Field(default=None, description="Opcional: ID de categoría específica")
    discount_percentage: Decimal = Field(ge=5, le=90, description="Porcentaje de liquidación a aplicar (ej. 40% a 60%)")
    is_clearance: bool = True

class ProductResponse(ORMModel):
    id: int; category_id: int; season_id: int | None
    name: str; brand: str | None; price: Decimal
    wholesale_price: Decimal | None = None
    wholesale_min_quantity: int = 3
    material: str | None = None
    secondary_color: str | None = None
    is_clearance: bool = False
    discount_percentage: Decimal = Decimal("0.00")
    is_active: bool
    category_name: str | None = None
    tenant_id: int | None = None
    model_3d_url: str | None = None; model_3d_format: str | None = None; technical_metadata: str | None = None
    variants: list[VariantResponse] = []