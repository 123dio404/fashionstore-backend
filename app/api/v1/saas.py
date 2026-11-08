from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.core.security import get_password_hash
from app.models.tenant import Tenant, Plan, Subscription
from app.models.branch import Branch
from app.models.user import User, Rol, Role
from app.schemas.saas import (
    PlanResponse,
    PlanCreate,
    PlanUpdate,
    SubscriptionResponse,
    TenantSummaryResponse,
    ChangePlanRequest,
    TenantCreateRequest,
    TenantStatusUpdate,
)
from app.services.auth_service import normalize_email

router = APIRouter(prefix="/saas", tags=["saas"])


@router.get("/plans", response_model=list[PlanResponse])
def list_plans(include_inactive: bool = False, db: Session = Depends(get_db)):
    """Lista los planes de suscripción configurados. El panel SaaS puede pedir también los inactivos."""
    query = select(Plan).order_by(Plan.monthly_price)
    if not include_inactive:
        query = query.where(Plan.is_active == True)
    return db.scalars(query).all()


@router.post("/plans", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
def create_plan(
    data: PlanCreate,
    user: User = Depends(require_role(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    """Superadministrador: crea un nuevo plan comercial."""
    if db.scalar(select(Plan).where(func.lower(Plan.name) == data.name.lower().strip())):
        raise HTTPException(status_code=409, detail="Ya existe un plan con ese nombre")
    plan = Plan(**data.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.patch("/plans/{plan_id}", response_model=PlanResponse)
def update_plan(
    plan_id: int,
    data: PlanUpdate,
    user: User = Depends(require_role(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    """Superadministrador: edita límites, precio o disponibilidad de un plan."""
    plan = db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    values = data.model_dump(exclude_unset=True)
    if "name" in values:
        values["name"] = values["name"].strip()
        duplicate = db.scalar(
            select(Plan).where(
                func.lower(Plan.name) == values["name"].lower(),
                Plan.id != plan_id,
            )
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Ya existe un plan con ese nombre")

    for key, value in values.items():
        setattr(plan, key, value)
    db.commit()
    db.refresh(plan)
    return plan


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(
    plan_id: int,
    user: User = Depends(require_role(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    """Superadministrador: elimina un plan que no tenga suscripciones asociadas."""
    plan = db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    in_use = db.scalar(select(func.count(Subscription.id)).where(Subscription.plan_id == plan_id)) or 0
    if in_use:
        raise HTTPException(
            status_code=409,
            detail="El plan tiene suscripciones asociadas. Desactívelo en lugar de eliminarlo.",
        )
    db.delete(plan)
    db.commit()


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
    tenant_id = data.tenant_id or user.tenant_id
    if data.tenant_id is not None and user.role != Role.SUPERADMIN:
        raise HTTPException(
            status_code=403,
            detail="Solo el Superadministrador puede cambiar el plan de otra empresa",
        )
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Debe pertenecer a una empresa para cambiar de plan")

    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    clean_name = data.plan_name.lower().strip()
    if clean_name in ("basico", "básico"):
        target_plan = db.scalar(select(Plan).where(Plan.name == "Básico"))
    elif clean_name in ("profesional",):
        target_plan = db.scalar(select(Plan).where(Plan.name == "Profesional"))
    elif clean_name in ("empresarial",):
        target_plan = db.scalar(select(Plan).where(Plan.name == "Empresarial"))
    else:
        target_plan = db.scalar(select(Plan).where(func.lower(Plan.name) == clean_name))

    if not target_plan:
        raise HTTPException(
            status_code=404,
            detail=f"Plan '{data.plan_name}' no encontrado. Opciones: 'Básico', 'Profesional', 'Empresarial'",
        )

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

    # Notificaciones coherentes: Superadmin (aviso financiero de cobro SaaS) y Tenant Admin (confirmación)
    try:
        from app.services.notification_service import notify_subscription_payment
        total_amount = target_plan.monthly_price * Decimal(str(data.months))
        notify_subscription_payment(
            db=db,
            tenant=tenant,
            plan=target_plan,
            months=data.months,
            total_amount=total_amount,
        )
        db.commit()
    except Exception:
        pass

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


@router.patch("/tenants/{tenant_id}/status", response_model=TenantSummaryResponse)
def update_tenant_status(
    tenant_id: int,
    data: TenantStatusUpdate,
    user: User = Depends(require_role(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    """Superadministrador: Suspender o reactivar una empresa por falta de pago o política SaaS (Punto 5)."""
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    clean_status = data.status.capitalize()
    if clean_status not in ("Activo", "Suspendido"):
        raise HTTPException(status_code=400, detail="El estado debe ser 'Activo' o 'Suspendido'")

    tenant.status = clean_status
    if tenant.subscription:
        tenant.subscription.status = "Activa" if clean_status == "Activo" else "Suspendida"

    db.commit()
    db.refresh(tenant)

    # Notificaciones de estado de empresa (Superadmin & Tenant Admin)
    try:
        from app.services.notification_service import notify_tenant_status_change
        notify_tenant_status_change(db=db, tenant=tenant, new_status=clean_status)
        db.commit()
    except Exception:
        pass

    active_b = db.scalar(
        select(func.count(Branch.id)).where(Branch.tenant_id == tenant.id, Branch.is_active == True)
    ) or 0

    return TenantSummaryResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        tax_id=tenant.tax_id,
        status=tenant.status,
        created_at=tenant.created_at,
        active_branches_count=active_b,
        subscription=tenant.subscription,
    )



def _resolve_plan(db: Session, plan_name: str, active_only: bool = False) -> Plan:
    clean_name = plan_name.lower().strip()
    if clean_name in ("basico", "básico"):
        query = select(Plan).where(Plan.name == "Básico")
    elif clean_name in ("profesional",):
        query = select(Plan).where(Plan.name == "Profesional")
    elif clean_name in ("empresarial",):
        query = select(Plan).where(Plan.name == "Empresarial")
    else:
        query = select(Plan).where(func.lower(Plan.name) == clean_name)
    if active_only:
        query = query.where(Plan.is_active == True)
    plan = db.scalar(query)
    if not plan:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Plan '{plan_name}' no encontrado o no disponible. "
                "Opciones: 'Básico', 'Profesional' o 'Empresarial'"
            ),
        )
    return plan


def _provision_tenant(
    db: Session, data: TenantCreateRequest, active_only: bool = False
) -> TenantSummaryResponse:
    """Crea empresa + suscripción + usuario administrador inicial (alta compartida)."""
    existing = db.scalar(select(Tenant).where((Tenant.slug == data.slug) | (Tenant.name == data.name)))
    if existing:
        raise HTTPException(status_code=409, detail="Ya existe una empresa con ese nombre o slug")

    plan = _resolve_plan(db, data.plan_name, active_only=active_only)

    norm_email = normalize_email(data.admin_email)
    existing_user = db.scalar(select(User).where(User.email == norm_email))
    if existing_user:
        raise HTTPException(status_code=409, detail="El correo del administrador ya está registrado")

    now = datetime.now(timezone.utc)
    new_tenant = Tenant(
        name=data.name,
        slug=data.slug,
        tax_id=data.tax_id,
        status="Activo",
    )
    db.add(new_tenant)
    db.flush()

    sub = Subscription(
        tenant_id=new_tenant.id,
        plan_id=plan.id,
        start_date=now,
        end_date=now + timedelta(days=365),
        status="Activa",
    )
    db.add(sub)

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

    # Notificaciones: Aviso de nueva empresa al Superadmin del SaaS y bienvenida al Admin
    try:
        from app.services.notification_service import send_notification
        send_notification(
            db=db,
            tenant_id=None,
            target_role=Role.SUPERADMIN.value,
            title="🏢 Nueva Empresa Registrada",
            message=f"Se registró '{new_tenant.name}' en la plataforma con el Plan {plan.name} (Bs. {plan.monthly_price}/mes). Administrador: {data.admin_name}.",
            notif_type="system",
            link="/admin/tenants",
        )
        send_notification(
            db=db,
            tenant_id=new_tenant.id,
            target_role=Role.ADMINISTRADOR.value,
            title="👋 ¡Bienvenido a FashionStore SaaS!",
            message=f"Tu empresa '{new_tenant.name}' está activa con el Plan {plan.name}. Puedes configurar sucursales, catálogo y personal.",
            notif_type="system",
            link="/admin/branches",
        )
        db.commit()
    except Exception:
        pass

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


@router.post("/tenants", response_model=TenantSummaryResponse, status_code=status.HTTP_201_CREATED)
def create_tenant(
    data: TenantCreateRequest,
    user: User = Depends(require_role(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    """Superadministrador: Da de alta una nueva empresa contratante y crea su usuario Administrador inicial."""
    return _provision_tenant(db, data)


@router.post("/register-store", response_model=TenantSummaryResponse, status_code=status.HTTP_201_CREATED)
def register_store(data: TenantCreateRequest, db: Session = Depends(get_db)):
    """Autoservicio público: una tienda crea su empresa, suscripción y cuenta de administrador."""
    return _provision_tenant(db, data, active_only=True)
