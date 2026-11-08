from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.user import Role

if TYPE_CHECKING:
    from app.models.branch import Branch
    from app.models.commerce import Reservation, Sale
    from app.models.inventory import Stock
    from app.models.tenant import Plan, Tenant
    from app.models.user import User


def send_notification(
    db: Session,
    title: str,
    message: str,
    tenant_id: int | None = None,
    user_id: int | None = None,
    target_role: str | None = None,
    notif_type: str = "system",
    link: str | None = None,
) -> Notification:
    """Inserta una notificación en la base de datos para un usuario o rol específico."""
    notif = Notification(
        tenant_id=tenant_id,
        user_id=user_id,
        target_role=target_role,
        title=title,
        message=message,
        type=notif_type,
        link=link,
        is_read=False,
    )
    db.add(notif)
    return notif


# --------------------------------------------------------------------------- #
# Eventos de Comercio (Ventas Online & POS)                                    #
# --------------------------------------------------------------------------- #

def notify_online_checkout(
    db: Session,
    sale: Sale,
    branch: Branch,
    client: User | None,
    total: Decimal,
    invoice_number: str | None = None,
) -> None:
    """
    Notifica la compra en línea:
    - Cliente: Confirmación de su pedido con número de factura.
    - Administrador de la tienda: Notificación de ingreso y venta digital.
    - Encargado de la sucursal: Alerta para preparar despacho o retiro en tienda.
    """
    client_name = client.full_name if client else "Cliente"
    tenant_id = branch.tenant_id

    # 1. Al Cliente comprador
    if sale.client_id:
        inv_text = f" (Factura {invoice_number})" if invoice_number else ""
        send_notification(
            db=db,
            tenant_id=tenant_id,
            user_id=sale.client_id,
            target_role=Role.CLIENTE.value,
            title="🛍️ ¡Compra Confirmada!",
            message=f"Tu pedido #{sale.id} por Bs. {total:.2f}{inv_text} fue procesado con éxito. Puedes ver el detalle y comprobante en tus compras.",
            notif_type="purchase_success",
            link="/purchases",
        )

    # 2. Al Administrador de la tienda (Dueño)
    send_notification(
        db=db,
        tenant_id=tenant_id,
        target_role=Role.ADMINISTRADOR.value,
        title="💰 Nueva Venta Online",
        message=f"Venta digital #{sale.id} por Bs. {total:.2f} en '{branch.name}'. Comprador: {client_name}.",
        notif_type="system",
        link="/admin/sales",
    )

    # 3. Al Encargado de la sucursal asignada
    send_notification(
        db=db,
        tenant_id=tenant_id,
        target_role=Role.ENCARGADO.value,
        title="📦 Nuevo Pedido para Preparar",
        message=f"Pedido #{sale.id} por Bs. {total:.2f} recibido en '{branch.name}'. Preparar prendas para entrega/retiro de {client_name}.",
        notif_type="system",
        link="/inventory",
    )


def notify_pos_sale(
    db: Session,
    sale: Sale,
    branch: Branch,
    cashier: User | None,
    client: User | None,
    total: Decimal,
) -> None:
    """
    Notifica una venta presencial en POS:
    - Cajero: Registro y confirmación del cobro en su mostrador.
    - Cliente: Ticket digital si es cliente registrado.
    - Administrador: Registro de cobro en mostrador.
    """
    tenant_id = branch.tenant_id
    cashier_name = cashier.full_name if cashier else "Cajero"

    # 1. Al Cajero que operó la terminal POS
    if sale.user_id:
        send_notification(
            db=db,
            tenant_id=tenant_id,
            user_id=sale.user_id,
            target_role=Role.CAJERO.value,
            title="🏷️ Venta POS Completada",
            message=f"Cobro exitoso de Venta #{sale.id} por Bs. {total:.2f} en '{branch.name}'. Comprobante emitido.",
            notif_type="purchase_success",
            link="/pos",
        )

    # 2. Al Cliente registrado (si no es consumidor final anónimo)
    if sale.client_id and client and client.role == Role.CLIENTE:
        send_notification(
            db=db,
            tenant_id=tenant_id,
            user_id=sale.client_id,
            target_role=Role.CLIENTE.value,
            title="🧾 Ticket de Compra en Tienda",
            message=f"Gracias por tu compra en '{branch.name}'. Venta #{sale.id} por Bs. {total:.2f} registrada.",
            notif_type="purchase_success",
            link="/purchases",
        )

    # 3. Al Administrador de la tienda
    send_notification(
        db=db,
        tenant_id=tenant_id,
        target_role=Role.ADMINISTRADOR.value,
        title="💵 Cobro en Caja POS",
        message=f"Venta en mostrador #{sale.id} por Bs. {total:.2f} cobrada en '{branch.name}' por {cashier_name}.",
        notif_type="system",
        link="/admin/sales",
    )


# --------------------------------------------------------------------------- #
# Eventos de Reservas de Probador (O2O)                                        #
# --------------------------------------------------------------------------- #

def notify_reservation_created(
    db: Session,
    reservation: Reservation,
    branch: Branch,
    client: User | None,
) -> None:
    """
    Notifica la creación de una reserva de probador:
    - Cliente: Confirmación de su cita con fecha, hora y sucursal.
    - Encargado: Agenda de la sucursal.
    - Cajero: Cita prevista en la tienda.
    """
    tenant_id = branch.tenant_id
    client_name = client.full_name if client else "Cliente"
    time_str = reservation.reservation_time.strftime("%H:%M") if hasattr(reservation.reservation_time, "strftime") else str(reservation.reservation_time)
    date_str = str(reservation.reservation_date)

    # 1. Al Cliente
    if reservation.client_id:
        send_notification(
            db=db,
            tenant_id=tenant_id,
            user_id=reservation.client_id,
            target_role=Role.CLIENTE.value,
            title="📅 ¡Reserva de Probador Confirmada!",
            message=f"Tu cita en '{branch.name}' para el {date_str} a las {time_str} fue reservada. Presenta el código #{reservation.id} al llegar.",
            notif_type="reservation",
            link="/my-reservations",
        )

    # 2. Al Encargado de la sucursal
    send_notification(
        db=db,
        tenant_id=tenant_id,
        target_role=Role.ENCARGADO.value,
        title="🗓️ Nueva Cita de Probador",
        message=f"El cliente {client_name} agendó probador en '{branch.name}' para el {date_str} a las {time_str} (Reserva #{reservation.id}).",
        notif_type="reservation",
        link="/reservations",
    )

    # 3. Al Cajero de la sucursal
    send_notification(
        db=db,
        tenant_id=tenant_id,
        target_role=Role.CAJERO.value,
        title="👗 Reserva Programada en Sucursal",
        message=f"Cita #{reservation.id} para hoy {date_str} a las {time_str} en '{branch.name}' ({client_name}).",
        notif_type="reservation",
        link="/pos",
    )


# --------------------------------------------------------------------------- #
# Eventos de Caja / Arqueo                                                    #
# --------------------------------------------------------------------------- #

def notify_cash_close(
    db: Session,
    branch: Branch,
    cashier: User | None,
    total_sales: Decimal,
    sales_count: int,
    diff: Decimal,
    status_text: str,
) -> None:
    """
    Notifica el cierre de turno y arqueo de caja:
    - Administrador: Resumen de recaudación, ventas y diferencias de gaveta.
    - Cajero: Confirmación de su cierre de turno.
    """
    tenant_id = branch.tenant_id
    cashier_name = cashier.full_name if cashier else "Cajero"

    # 1. Al Administrador de la tienda
    send_notification(
        db=db,
        tenant_id=tenant_id,
        target_role=Role.ADMINISTRADOR.value,
        title=f"💵 Arqueo y Cierre de Caja · {branch.name}",
        message=f"El cajero {cashier_name} cerró turno en '{branch.name}'. Total recaudado: Bs. {total_sales:.2f} ({sales_count} ventas). Arqueo: {status_text}.",
        notif_type="system",
        link="/admin/sales",
    )

    # 2. Al Cajero
    if cashier:
        send_notification(
            db=db,
            tenant_id=tenant_id,
            user_id=cashier.id,
            target_role=Role.CAJERO.value,
            title="✅ Turno de Caja Cerrado",
            message=f"Tu turno en '{branch.name}' fue cerrado exitosamente. Recaudación total: Bs. {total_sales:.2f}. Comprobante emitido.",
            notif_type="system",
            link="/pos",
        )


# --------------------------------------------------------------------------- #
# Eventos de Suscripción SaaS (Superadmin & Tenant Admin)                      #
# --------------------------------------------------------------------------- #

def notify_subscription_payment(
    db: Session,
    tenant: Tenant,
    plan: Plan,
    months: int,
    total_amount: Decimal,
) -> None:
    """
    Notifica el pago o renovación de una suscripción SaaS:
    - Superadmin: Notificación financiera con el cobro facturado a la empresa.
    - Administrador del Tenant: Confirmación de su plan, vigencia y límites.
    """
    # 1. Al Superadmin del SaaS (Global)
    send_notification(
        db=db,
        tenant_id=None,
        target_role=Role.SUPERADMIN.value,
        title="💳 Pago de Suscripción SaaS Recibido",
        message=f"La empresa '{tenant.name}' contrató/renovó el Plan {plan.name} por Bs. {plan.monthly_price}/mes ({months} meses). Ingreso facturado: Bs. {total_amount:.2f}.",
        notif_type="billing_reminder",
        link="/admin/tenants",
    )

    # 2. Al Administrador de la tienda (Dueño del Tenant)
    send_notification(
        db=db,
        tenant_id=tenant.id,
        target_role=Role.ADMINISTRADOR.value,
        title="🎉 Suscripción SaaS Actualizada",
        message=f"Tu empresa '{tenant.name}' activó exitosamente el Plan {plan.name} (Bs. {plan.monthly_price}/mes). Sucursales permitidas: {plan.max_branches}. IA: {'Habilitada' if plan.has_ai_reports else 'No incluida'}.",
        notif_type="subscription_alert",
        link="/admin/subscription",
    )


def notify_tenant_status_change(
    db: Session,
    tenant: Tenant,
    new_status: str,
    reason: str | None = None,
) -> None:
    """
    Notifica el cambio de estado de una tienda (ej: Suspendido por morosidad o Reactivado):
    - Superadmin: Registro de la acción.
    - Administrador del Tenant: Notificación de alerta o confirmación de reactivación.
    """
    # 1. Al Superadmin
    send_notification(
        db=db,
        tenant_id=None,
        target_role=Role.SUPERADMIN.value,
        title="⚖️ Estado de Empresa Actualizado",
        message=f"La empresa '{tenant.name}' cambió a estado '{new_status}'.",
        notif_type="system",
        link="/admin/tenants",
    )

    # 2. Al Administrador de la tienda
    is_suspended = new_status == "Suspendido"
    send_notification(
        db=db,
        tenant_id=tenant.id,
        target_role=Role.ADMINISTRADOR.value,
        title=f"{'⚠️ Alerta: Empresa Suspendida' if is_suspended else '✅ Empresa Reactivada'}",
        message=(
            f"Tu empresa '{tenant.name}' ha sido suspendida temporalmente por mora en la suscripción SaaS. "
            f"Las ventas y reservas estarán bloqueadas hasta regularizar el pago en 'Planes y Suscripción'."
            if is_suspended
            else f"Tu empresa '{tenant.name}' se encuentra activa. Todas las operaciones de caja y catálogo están habilitadas."
        ),
        notif_type="subscription_alert",
        link="/admin/subscription",
    )


# --------------------------------------------------------------------------- #
# Eventos de Stock Crítico                                                    #
# --------------------------------------------------------------------------- #

def notify_stock_critical(
    db: Session,
    branch: Branch,
    stock: Stock,
    prod_name: str,
    size_name: str,
    color_name: str,
) -> None:
    """
    Notifica cuando una prenda llega a nivel crítico:
    - Administrador: Notificación de compra/reposición a proveedores.
    - Encargado: Alerta operativa de tienda.
    """
    tenant_id = branch.tenant_id
    detail = f"La prenda '{prod_name}' (Talla {size_name}, Color {color_name}) en la sucursal '{branch.name}' tiene solo {stock.physical_stock} unidades disponibles."

    # 1. Al Administrador
    send_notification(
        db=db,
        tenant_id=tenant_id,
        target_role=Role.ADMINISTRADOR.value,
        title="⚠️ Alerta de Stock Crítico",
        message=f"{detail} Se sugiere emitir orden de reposición con proveedores.",
        notif_type="system",
        link="/admin/inventory",
    )

    # 2. Al Encargado
    send_notification(
        db=db,
        tenant_id=tenant_id,
        target_role=Role.ENCARGADO.value,
        title="⚠️ Reposición Urgente en Sucursal",
        message=f"{detail} Revisar existencias y coordinar reposición de tienda.",
        notif_type="system",
        link="/inventory",
    )
