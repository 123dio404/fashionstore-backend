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


class PlanCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    max_branches: int = Field(ge=1, le=10000)
    has_ai_reports: bool = False
    monthly_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    is_active: bool = True


class PlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    max_branches: int | None = Field(default=None, ge=1, le=10000)
    has_ai_reports: bool | None = None
    monthly_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    is_active: bool | None = None


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


class TenantStatusUpdate(BaseModel):
    status: str = Field(description="Estado de la empresa: 'Activo' o 'Suspendido'")


class ChangePlanRequest(BaseModel):
    plan_name: str = Field(description="Nombre del plan: 'Básico', 'Profesional' o 'Empresarial'")
    months: int = Field(default=12, ge=1, le=36, description="Meses de vigencia para la suscripción simulada")
    tenant_id: int | None = Field(
        default=None,
        description="Solo Superadmin: empresa objetivo. Los administradores solo pueden cambiar la propia.",
    )


class TenantCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=150, description="Razón Social / Nombre de la empresa")
    slug: str = Field(min_length=2, max_length=100, description="Identificador único (ej: zara-bolivia)")
    tax_id: str | None = Field(default=None, description="NIT o documento fiscal")
    plan_name: str = Field(default="Básico", description="Plan inicial: 'Básico', 'Profesional' o 'Empresarial'")
    admin_email: str = Field(description="Email del administrador de la empresa")
    admin_name: str = Field(default="Administrador", description="Nombre completo del administrador")
    admin_password: str = Field(default="Admin123", min_length=6, description="Contraseña inicial del administrador")
