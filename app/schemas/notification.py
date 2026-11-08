from datetime import datetime
from pydantic import BaseModel, Field
from app.schemas.common import ORMModel


class NotificationResponse(ORMModel):
    id: int
    tenant_id: int | None = None
    user_id: int | None = None
    target_role: str | None = None
    title: str
    message: str
    type: str
    link: str | None = None
    is_read: bool
    created_at: datetime


class TenantBroadcastRequest(BaseModel):
    """Solicitud del Superadmin para notificar a los dueños de tiendas."""
    tenant_ids: list[int] | None = Field(
        default=None,
        description="IDs de las empresas destinatarias. Si es None o vacío, se envía a todos los dueños de tiendas.",
    )
    title: str = Field(min_length=3, max_length=200)
    message: str = Field(min_length=5)
    type: str = Field(
        default="billing_reminder",
        description="billing_reminder, subscription_alert, system, maintenance",
    )
    link: str | None = Field(default="/admin/subscription", max_length=300)


class CustomerBroadcastRequest(BaseModel):
    """Solicitud del Dueño de Tienda para notificar a todos los clientes de su tienda."""
    title: str = Field(min_length=3, max_length=200)
    message: str = Field(min_length=5)
    type: str = Field(
        default="promotion",
        description="promotion, flash_sale, new_collection, event",
    )
    link: str | None = Field(default="/promotions", max_length=300)


class BroadcastResultResponse(BaseModel):
    detail: str
    count: int
    type: str
