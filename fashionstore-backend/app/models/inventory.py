import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.branch import Branch
    from app.models.product import ProductVariant
    from app.models.user import User


class MovementType(str, enum.Enum):
    INGRESO = "ingreso"
    TRANSFERENCIA = "transferencia"
    AJUSTE = "ajuste"


class Stock(Base):
    __tablename__ = "stocks"
    __table_args__ = (
        UniqueConstraint("branch_id", "variant_id", name="uq_stock_branch_variant"),
        CheckConstraint("physical_stock >= 0", name="ck_stock_physical_non_negative"),
        CheckConstraint("reserved_stock >= 0", name="ck_stock_reserved_non_negative"),
        CheckConstraint("reserved_stock <= physical_stock", name="ck_stock_reserved_lte_physical"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    branch_id: Mapped[UUID] = mapped_column(ForeignKey("branches.id", ondelete="CASCADE"), index=True)
    variant_id: Mapped[UUID] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"), index=True
    )
    physical_stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reserved_stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    branch: Mapped["Branch"] = relationship(back_populates="stocks")
    variant: Mapped["ProductVariant"] = relationship(back_populates="stocks")

    @property
    def available_stock(self) -> int:
        return self.physical_stock - self.reserved_stock


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    movement_type: Mapped[MovementType] = mapped_column(
        Enum(MovementType, name="movement_type", native_enum=False), index=True
    )
    variant_id: Mapped[UUID] = mapped_column(ForeignKey("product_variants.id", ondelete="RESTRICT"))
    source_branch_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="RESTRICT"), nullable=True
    )
    destination_branch_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="RESTRICT"), nullable=True
    )
    quantity: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    performed_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    variant: Mapped["ProductVariant"] = relationship()
    source_branch: Mapped["Branch | None"] = relationship(foreign_keys=[source_branch_id])
    destination_branch: Mapped["Branch | None"] = relationship(foreign_keys=[destination_branch_id])
    performed_by: Mapped["User"] = relationship()
