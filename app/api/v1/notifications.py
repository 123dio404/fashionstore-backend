from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.models.notification import Notification
from app.models.tenant import Tenant
from app.models.user import Role, User
from app.schemas.notification import (
    BroadcastResultResponse,
    CustomerBroadcastRequest,
    NotificationResponse,
    TenantBroadcastRequest,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/me", response_model=list[NotificationResponse])
def get_my_notifications(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Obtiene las notificaciones relevantes para el usuario actual:
    - Notificaciones directas a su ID de usuario.
    - Notificaciones dirigidas al rol del usuario dentro de su empresa (tenant).
    - Notificaciones globales dirigidas a su rol.
    """
    role_str = current_user.role.value if current_user.role else "Cliente"
    tenant_id = current_user.tenant_id

    # Filtros según jerarquía y tenant
    conditions = [Notification.user_id == current_user.id]

    if current_user.role == Role.SUPERADMIN:
        # Superadmin ve notificaciones directas o globales de superadmin
        conditions.append(
            (Notification.tenant_id.is_(None)) & (Notification.target_role == Role.SUPERADMIN.value)
        )
    else:
        # Usuarios asociados a un tenant:
        # 1. Notificaciones dirigidas a su tenant y su rol
        conditions.append(
            (Notification.tenant_id == tenant_id)
            & (or_(Notification.target_role == role_str, Notification.target_role.is_(None)))
        )
        # 2. Notificaciones globales de la plataforma para su rol
        conditions.append(
            (Notification.tenant_id.is_(None))
            & (or_(Notification.target_role == role_str, Notification.target_role.is_(None)))
        )

    stmt = (
        select(Notification)
        .where(or_(*conditions))
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    return db.scalars(stmt).all()


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_as_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Marca una notificación como leída."""
    notif = db.get(Notification, notification_id)
    if not notif:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")

    # Verificar que el usuario tenga acceso a esta notificación
    if notif.user_id and notif.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permiso para esta notificación")
    if notif.tenant_id and current_user.role != Role.SUPERADMIN and notif.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="No tienes permiso para esta notificación")

    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return notif


@router.post(
    "/broadcast-tenants",
    response_model=BroadcastResultResponse,
    dependencies=[Depends(require_role(Role.SUPERADMIN))],
)
def broadcast_to_tenants(
    data: TenantBroadcastRequest,
    db: Session = Depends(get_db),
):
    """
    [Superadmin] Envía notificaciones a los dueños/administradores de tiendas
    (ej: recordatorios de pago de suscripción, aviso de corte, mantenimiento del SaaS).
    """
    # Determinar tenants destinatarios
    if data.tenant_ids and len(data.tenant_ids) > 0:
        tenants = db.scalars(select(Tenant).where(Tenant.id.in_(data.tenant_ids))).all()
    else:
        tenants = db.scalars(select(Tenant).where(Tenant.status == "Activo")).all()

    if not tenants:
        raise HTTPException(status_code=404, detail="No se encontraron empresas destinatarias")

    created_count = 0
    for t in tenants:
        notif = Notification(
            tenant_id=t.id,
            target_role=Role.ADMINISTRADOR.value,
            title=data.title,
            message=data.message,
            type=data.type,
            link=data.link or "/admin/subscription",
            is_read=False,
        )
        db.add(notif)
        created_count += 1

    db.commit()
    return BroadcastResultResponse(
        detail=f"Notificación push enviada a {created_count} empresas (dueños de tienda).",
        count=created_count,
        type=data.type,
    )


@router.post(
    "/broadcast-customers",
    response_model=BroadcastResultResponse,
    dependencies=[Depends(require_role(Role.SUPERADMIN, Role.ADMINISTRADOR))],
)
def broadcast_to_customers(
    data: CustomerBroadcastRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    [Dueño de Tienda / Admin Tenant] Envía notificaciones push a todos sus clientes
    para promociones, rebajas, nueva temporada o eventos especiales.
    """
    tenant_id = current_user.tenant_id
    if not tenant_id and current_user.role != Role.SUPERADMIN:
        raise HTTPException(status_code=400, detail="El usuario no pertenece a ninguna empresa")

    notif = Notification(
        tenant_id=tenant_id,
        target_role=Role.CLIENTE.value,
        title=data.title,
        message=data.message,
        type=data.type,
        link=data.link or "/promotions",
        is_read=False,
    )
    db.add(notif)
    db.commit()

    return BroadcastResultResponse(
        detail="Campaña de notificación promocional enviada exitosamente a los clientes de la tienda.",
        count=1,
        type=data.type,
    )

