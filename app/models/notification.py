from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.user import User


class Notification(Base):
    """
    Notificaciones del sistema y campañas push:
    - Superadmin -> Dueños de tiendas (recordatorios de pago de suscripción, avisos de corte, mantenimiento).
    - Dueños de tienda (Tenant Admins) -> Clientes (promociones, nueva colección, descuentos).
    - Sistema -> Notificaciones transaccionales a usuarios individuales.
    """
    __tablename__ = "notificacion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int | None] = mapped_column(
        "id_empresa", ForeignKey("empresa.id", ondelete="CASCADE"), nullable=True, index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        "id_usuario", ForeignKey("usuario.id", ondelete="CASCADE"), nullable=True, index=True
    )
    target_role: Mapped[str | None] = mapped_column("rol_objetivo", String(50), nullable=True, index=True)
    title: Mapped[str] = mapped_column("titulo", String(200), nullable=False)
    message: Mapped[str] = mapped_column("mensaje", Text, nullable=False)
    type: Mapped[str] = mapped_column(
        "tipo", String(50), default="system", nullable=False, index=True
    )  # billing_reminder, subscription_alert, promotion, system, order
    link: Mapped[str | None] = mapped_column("enlace", String(300), nullable=True)
    is_read: Mapped[bool] = mapped_column("leido", Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        "fecha_creacion", DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tenant: Mapped["Tenant | None"] = relationship()
    user: Mapped["User | None"] = relationship()

