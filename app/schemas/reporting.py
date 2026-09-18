from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PurchaseHistoryItem(BaseModel):
    product_id: int
    product_name: str
    variant_id: int
    quantity: int
    unit_price: Decimal
    subtotal: Decimal


class PurchaseHistoryEntry(BaseModel):
    sale_id: int
    sale_date: datetime
    branch_id: int
    sale_type: str
    total: Decimal
    items: list[PurchaseHistoryItem]


class PurchaseHistoryResponse(BaseModel):
    client_id: int
    start_date: datetime | None
    end_date: datetime | None
    total_orders: int
    total_spent: Decimal
    purchases: list[PurchaseHistoryEntry]


class SalesReportRow(BaseModel):
    key: str
    orders: int
    units: int
    revenue: Decimal


class SalesReportResponse(BaseModel):
    start_date: datetime
    end_date: datetime
    total_orders: int
    total_units: int
    total_revenue: Decimal
    average_order_value: Decimal
    by_channel: list[SalesReportRow]
    by_branch: list[SalesReportRow]
    by_day: list[SalesReportRow]


class InventoryReportRow(BaseModel):
    stock_id: int
    branch_id: int
    product_id: int
    product_name: str
    variant_id: int
    physical_stock: int
    reserved_stock: int
    available_stock: int
    min_stock: int
    below_minimum: bool


class InventoryReportResponse(BaseModel):
    generated_at: datetime
    total_skus: int
    total_physical_units: int
    total_available_units: int
    low_stock_count: int
    stock: list[InventoryReportRow]


class DashboardResponse(BaseModel):
    start_date: datetime
    end_date: datetime
    total_orders: int
    total_units: int
    total_revenue: Decimal
    average_order_value: Decimal
    low_stock_count: int
    inventory_value: Decimal
    top_products: list[dict[str, Any]]
    channels: list[SalesReportRow]


class AnalyticalQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    client_id: int | None = Field(default=None, ge=1)
    audio: dict[str, Any] | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None


class AnalyticalQueryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    query: str
    intent: str
    parameters: dict[str, Any]
    result: dict[str, Any]
