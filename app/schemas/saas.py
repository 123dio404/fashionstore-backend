from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field
from app.schemas.common import ORMModel


class PlanResponse(ORMModel):
    id: int
    name: str
    max_branches: int
    has_ai_reports: bool
    monthly_price: Decimal
    is_active: bool


class SubscriptionResponse(ORMModel):
    id: int
    tenant_id: int
    plan_id: int
    start_date: datetime
    end_date: datetime | None
    status: str
    plan: PlanResponse | None = None


class TenantSummaryResponse(ORMModel):
    id: int
    name: str
    slug: str
    tax_id: str | None
    status: str
    created_at: datetime
    active_branches_count: int = 0
    subscription: SubscriptionResponse | None = None


class ChangePlanRequest(BaseModel):
    plan_name: str = Field(description="Nombre del plan: 'Básico' o 'Profesional'")
    months: int = Field(default=12, ge=1, le=36, description="Meses de vigencia para la suscripción simulada")


class TenantCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=150, description="Razón Social / Nombre de la empresa")
    slug: str = Field(min_length=2, max_length=100, description="Identificador único (ej: zara-bolivia)")
    tax_id: str | None = Field(default=None, description="NIT o documento fiscal")
    plan_name: str = Field(default="Básico", description="Plan inicial: 'Básico' o 'Profesional'")
    admin_email: str = Field(description="Email del administrador de la empresa")
    admin_name: str = Field(default="Administrador", description="Nombre completo del administrador")
    admin_password: str = Field(default="admin123", min_length=6, description="Contraseña inicial del administrador")
