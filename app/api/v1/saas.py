from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role, get_current_tenant_id
from app.core.security import get_password_hash
from app.models.tenant import Tenant, Plan, Subscription
from app.models.branch import Branch
from app.models.user import User, Rol, Role
from app.schemas.saas import (
    PlanResponse,
    SubscriptionResponse,
    TenantSummaryResponse,
    ChangePlanRequest,
    TenantCreateRequest,
)
from app.services.auth_service import normalize_email

router = APIRouter(prefix="/saas", tags=["saas"])


@router.get("/plans", response_model=list[PlanResponse])
def list_plans(db: Session = Depends(get_db)):
    """Lista todos los planes de suscripción configurados en la plataforma (Básico y Profesional)."""
    return db.scalars(select(Plan).where(Plan.is_active == True).order_by(Plan.monthly_price)).all()


@router.get("/my-subscription", response_model=TenantSummaryResponse)
def get_my_subscription(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retorna la información del tenant al que pertenece el usuario autenticado,
    su plan contratado, fecha de vencimiento y conteo de sucursales activas.
    """
    if not user.tenant_id:
        if user.role == Role.SUPERADMIN:
            raise HTTPException(
                status_code=400,
                detail="El Superadministrador global no pertenece a un tenant específico. Use /saas/tenants para listar todas las empresas."
            )
        raise HTTPException(status_code=403, detail="Usuario sin empresa asignada")

    tenant = db.get(Tenant, user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    # Contar sucursales activas
    active_branches = db.scalar(
        select(func.count(Branch.id)).where(Branch.tenant_id == tenant.id, Branch.is_active == True)
    ) or 0

    return TenantSummaryResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        tax_id=tenant.tax_id,
        status=tenant.status,
        created_at=tenant.created_at,
        active_branches_count=active_branches,
        subscription=tenant.subscription,
    )


@router.post("/change-plan", response_model=TenantSummaryResponse)
def change_plan(
    data: ChangePlanRequest,
    user: User = Depends(require_role(Role.ADMINISTRADOR, Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    """
    Simulación administrativa de contratación y cambio de plan SaaS (RN-02).
    Si se solicita bajar a Plan Básico, valida que la empresa no supere las 2 sucursales activas.
    """
    tenant_id = user.tenant_id
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Debe pertenecer a una empresa para cambiar de plan")

    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    target_plan = db.scalar(select(Plan).where(func.lower(Plan.name) == data.plan_name.lower().strip()))
    if not target_plan:
        raise HTTPException(status_code=404, detail=f"Plan '{data.plan_name}' no encontrado. Opciones: 'Básico', 'Profesional'")

    # Validar límites de sucursales activas si se reduce de plan
    active_branches = db.scalar(
        select(func.count(Branch.id)).where(Branch.tenant_id == tenant.id, Branch.is_active == True)
    ) or 0

    if active_branches > target_plan.max_branches:
        raise HTTPException(
            status_code=400,
            detail=(
                f"No puede cambiar al Plan {target_plan.name} porque tiene {active_branches} sucursales activas "
                f"y el plan solo permite un máximo de {target_plan.max_branches}. Desactive las sucursales sobrantes primero."
            )
        )

    # Actualizar o crear suscripción
    sub = tenant.subscription
    now = datetime.now(timezone.utc)
    if not sub:
        sub = Subscription(
            tenant_id=tenant.id,
            plan_id=target_plan.id,
            start_date=now,
            end_date=now + timedelta(days=data.months * 30),
            status="Activa",
        )
        db.add(sub)
    else:
        sub.plan_id = target_plan.id
        sub.end_date = now + timedelta(days=data.months * 30)
        sub.status = "Activa"

    db.commit()
    db.refresh(tenant)

    return TenantSummaryResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        tax_id=tenant.tax_id,
        status=tenant.status,
        created_at=tenant.created_at,
        active_branches_count=active_branches,
        subscription=sub,
    )


@router.get("/tenants", response_model=list[TenantSummaryResponse])
def list_tenants(
    user: User = Depends(require_role(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    """Vista de Superadministrador global: Lista todas las empresas suscritas a la plataforma."""
    tenants = db.scalars(select(Tenant).order_by(Tenant.id)).all()
    results: list[TenantSummaryResponse] = []
    for t in tenants:
        active_b = db.scalar(
            select(func.count(Branch.id)).where(Branch.tenant_id == t.id, Branch.is_active == True)
        ) or 0
        results.append(
            TenantSummaryResponse(
                id=t.id,
                name=t.name,
                slug=t.slug,
                tax_id=t.tax_id,
                status=t.status,
                created_at=t.created_at,
                active_branches_count=active_b,
                subscription=t.subscription,
            )
        )
    return results


@router.post("/tenants", response_model=TenantSummaryResponse, status_code=status.HTTP_201_CREATED)
def create_tenant(
    data: TenantCreateRequest,
    user: User = Depends(require_role(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    """Superadministrador: Da de alta una nueva empresa contratante y crea su usuario Administrador inicial."""
    # Validar unicidad de slug o nombre
    existing = db.scalar(select(Tenant).where((Tenant.slug == data.slug) | (Tenant.name == data.name)))
    if existing:
        raise HTTPException(status_code=409, detail="Ya existe una empresa con ese nombre o slug")

    plan = db.scalar(select(Plan).where(func.lower(Plan.name) == data.plan_name.lower().strip()))
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{data.plan_name}' no encontrado")

    # Crear Tenant
    now = datetime.now(timezone.utc)
    new_tenant = Tenant(
        name=data.name,
        slug=data.slug,
        tax_id=data.tax_id,
        status="Activo",
    )
    db.add(new_tenant)
    db.flush()

    # Crear Suscripción inicial
    sub = Subscription(
        tenant_id=new_tenant.id,
        plan_id=plan.id,
        start_date=now,
        end_date=now + timedelta(days=365),
        status="Activa",
    )
    db.add(sub)

    # Crear Usuario Administrador de la Empresa
    norm_email = normalize_email(data.admin_email)
    existing_user = db.scalar(select(User).where(User.email == norm_email))
    if existing_user:
        raise HTTPException(status_code=409, detail="El correo del administrador ya está registrado")

    admin_role = db.scalar(select(Rol).where(Rol.nombre == "Administrador"))
    admin_user = User(
        email=norm_email,
        full_name=data.admin_name,
        password_hash=get_password_hash(data.admin_password),
        tenant_id=new_tenant.id,
        is_active=True,
    )
    if admin_role:
        admin_user.roles = [admin_role]
    db.add(admin_user)

    db.commit()
    db.refresh(new_tenant)

    return TenantSummaryResponse(
        id=new_tenant.id,
        name=new_tenant.name,
        slug=new_tenant.slug,
        tax_id=new_tenant.tax_id,
        status=new_tenant.status,
        created_at=new_tenant.created_at,
        active_branches_count=0,
        subscription=sub,
    )
