from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.branch import Branch
    from app.models.user import User


class Tenant(Base):
    """
    Empresa contratante (Tenant) en la plataforma SaaS.
    Cada tenant opera de manera lógica aislada con sus propias sucursales,
    usuarios, inventarios y operaciones comerciales.
    """
    __tablename__ = "empresa"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column("nombre", String(150), unique=True, index=True, nullable=False)
    tax_id: Mapped[str | None] = mapped_column("nit", String(50), nullable=True)
    slug: Mapped[str] = mapped_column("slug", String(100), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column("estado", String(30), default="Activo", nullable=False)
    created_at: Mapped[datetime] = mapped_column("fecha_creacion", DateTime(timezone=True), server_default=func.now(), nullable=False)

    subscription: Mapped["Subscription | None"] = relationship(back_populates="tenant", uselist=False, cascade="all, delete-orphan")
    branches: Mapped[list["Branch"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    users: Mapped[list["User"]] = relationship(back_populates="tenant")


class Plan(Base):
    """
    Planes de suscripción de la plataforma SaaS (Básico, Profesional).
    Configura límites operativos y acceso a módulos avanzados como IA.
    """
    __tablename__ = "plan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column("nombre", String(50), unique=True, nullable=False)
    max_branches: Mapped[int] = mapped_column("max_sucursales", Integer, default=2, nullable=False)
    has_ai_reports: Mapped[bool] = mapped_column("permite_ia", Boolean, default=False, nullable=False)
    monthly_price: Mapped[Decimal] = mapped_column("precio_mensual", Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    is_active: Mapped[bool] = mapped_column("estado", Boolean, default=True, nullable=False)

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="plan")


class Subscription(Base):
    """
    Suscripción de una empresa a un plan de FashionStore SaaS.
    Controla el periodo de vigencia y el estado de habilitación del servicio.
    """
    __tablename__ = "suscripcion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column("id_empresa", ForeignKey("empresa.id", ondelete="CASCADE"), unique=True, index=True)
    plan_id: Mapped[int] = mapped_column("id_plan", ForeignKey("plan.id", ondelete="RESTRICT"), index=True)
    start_date: Mapped[datetime] = mapped_column("fecha_inicio", DateTime(timezone=True), server_default=func.now(), nullable=False)
    end_date: Mapped[datetime | None] = mapped_column("fecha_fin", DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column("estado", String(30), default="Activa", nullable=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="subscription")
    plan: Mapped["Plan"] = relationship(back_populates="subscriptions")
