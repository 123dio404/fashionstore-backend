from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from app.models.customer_experience import FittingSessionStatus


class VirtualFittingSessionCreate(BaseModel):
    model_url: str | None = Field(default=None, max_length=500)
    model_format: str | None = Field(default=None, pattern=r"^(glb|gltf)$")
    model_metadata: dict[str, Any] | None = None


class VirtualFittingResultCreate(BaseModel):
    variant_id: int
    size_id: int | None = None
    result_url: str | None = Field(default=None, max_length=500)
    confidence: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    metadata: dict[str, Any] | None = None


class VirtualFittingResultResponse(VirtualFittingResultCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    metadata: dict[str, Any] | None = Field(default=None, alias="result_metadata")


class VirtualFittingSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    model_url: str | None
    model_format: str | None
    model_metadata: dict[str, Any] | None
    status: FittingSessionStatus
    created_at: datetime
    results: list[VirtualFittingResultResponse] = []


class VirtualFittingSessionStatusUpdate(BaseModel):
    status: FittingSessionStatus


class UserPreferenceUpsert(BaseModel):
    category_id: int | None = None
    preferred_brand: str | None = Field(default=None, max_length=100)
    preferred_colors: list[str] | None = None
    preferred_sizes: list[int] | None = None
    min_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    max_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)


class UserPreferenceResponse(UserPreferenceUpsert):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    updated_at: datetime


class RecommendationItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    score: Decimal
    reason: str | None


class RecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    recommendation_type: str
    created_at: datetime
    status: str
    items: list[RecommendationItemResponse] = []


class AnalyticsChannel(BaseModel):
    channel: str
    orders: int
    units: int
    revenue: Decimal


class InventoryRotation(BaseModel):
    product_id: int
    product_name: str
    units_sold: int
    current_stock: int
    rotation_rate: Decimal


class ExecutiveAnalyticsResponse(BaseModel):
    start_date: datetime
    end_date: datetime
    total_orders: int
    total_units: int
    total_revenue: Decimal
    average_order_value: Decimal
    channels: list[AnalyticsChannel]
    inventory_rotation: list[InventoryRotation]
