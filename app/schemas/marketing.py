from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    is_active: bool = True
    product_ids: list[int] = []


class CollectionResponse(CollectionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    product_ids: list[int] = []


class PromotionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    discount_type: str = Field(default="percentage", pattern="^(percentage|fixed)$")
    discount_value: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool = True
    product_ids: list[int] = []

    @model_validator(mode="after")
    def valid_dates(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must not exceed end_date")
        if self.discount_type == "percentage" and self.discount_value > 100:
            raise ValueError("percentage discount cannot exceed 100")
        return self


class PromotionResponse(PromotionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_ids: list[int] = []
