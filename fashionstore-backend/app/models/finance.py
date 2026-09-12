import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class FeeType(str, enum.Enum):
    CUOTA = "cuota"
    EXPENSA = "expensa"


class PaymentMethod(str, enum.Enum):
    TARJETA = "tarjeta"
    TRANSFERENCIA = "transferencia"
    EFECTIVO = "efectivo"


class PaymentStatus(str, enum.Enum):
    PENDIENTE = "pendiente"
    COMPLETADO = "completado"
    FALLIDO = "fallido"
    REEMBOLSADO = "reembolsado"


class FineStatus(str, enum.Enum):
    PENDIENTE = "pendiente"
    PAGADA = "pagada"
    ANULADA = "anulada"


class Fee(Base):
    __tablename__ = "fees"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_fee_amount_positive"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    fee_type: Mapped[FeeType] = mapped_column(
        Enum(FeeType, name="fee_type", native_enum=False), index=True
    )
    period: Mapped[str] = mapped_column(String(7), index=True)
    concept: Mapped[str] = mapped_column(String(200))
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    created_by: Mapped["User"] = relationship()
    payments: Mapped[list["Payment"]] = relationship(back_populates="fee", cascade="all, delete-orphan")


class Payment(Base):
    __tablename__ = "fee_payments"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    fee_id: Mapped[UUID] = mapped_column(ForeignKey("fees.id", ondelete="RESTRICT"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method", native_enum=False)
    )
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status", native_enum=False),
        default=PaymentStatus.PENDIENTE,
        index=True,
    )
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    fee: Mapped["Fee"] = relationship(back_populates="payments")
    payer: Mapped["User"] = relationship()


class Fine(Base):
    __tablename__ = "fines"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_fine_amount_positive"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    fee_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("fees.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str] = mapped_column(String(255))
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    status: Mapped[FineStatus] = mapped_column(
        Enum(FineStatus, name="fine_status", native_enum=False),
        default=FineStatus.PENDIENTE,
        index=True,
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship()
    fee: Mapped["Fee | None"] = relationship()