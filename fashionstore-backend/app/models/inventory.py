import enum
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.branch import Branch
    from app.models.product import ProductVariant


class MovementType(str, enum.Enum):
    INGRESO = "ingreso"
    TRANSFERENCIA = "transferencia"
    AJUSTE = "ajuste"
    VENTA = "venta"
    RESERVA = "reserva"


class Stock(Base):
    __tablename__ = "inventario"
    __table_args__ = (
        UniqueConstraint("id_sucursal", "id_variante", name="uq_inventario_sucursal_variante"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    branch_id: Mapped[int] = mapped_column("id_sucursal", ForeignKey("sucursal.id", ondelete="RESTRICT"), index=True)
    variant_id: Mapped[int] = mapped_column("id_variante", ForeignKey("producto_variante.id", ondelete="RESTRICT"), index=True)
    size_id: Mapped[int | None] = mapped_column("id_talla", ForeignKey("tallas.id", ondelete="RESTRICT"), nullable=True, index=True)
    physical_stock: Mapped[int] = mapped_column("stock_actual", Integer, default=0, nullable=False)
    min_stock: Mapped[int] = mapped_column("stock_minimo", Integer, default=0, nullable=False)
    reserved_stock: Mapped[int] = mapped_column("stock_reservado", Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column("fecha_actualizacion", DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    branch: Mapped["Branch"] = relationship(back_populates="stocks")
    variant: Mapped["ProductVariant"] = relationship(back_populates="stocks")
    size: Mapped["Size | None"] = relationship()
    movements: Mapped[list["InventoryMovement"]] = relationship(back_populates="inventory")

    @property
    def available_stock(self) -> int:
        return self.physical_stock - self.reserved_stock


class InventoryMovement(Base):
    __tablename__ = "movimiento_inventario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inventory_id: Mapped[int] = mapped_column("id_inventario", ForeignKey("inventario.id", ondelete="RESTRICT"), index=True)
    quantity: Mapped[int] = mapped_column("cantidad", Integer)
    created_at: Mapped[datetime] = mapped_column("fecha", DateTime(timezone=True), server_default=func.now(), nullable=False)
    reason: Mapped[str] = mapped_column("motivo", Text, default="")
    movement_type: Mapped[MovementType] = mapped_column(
        "tipo", Enum(MovementType, name="movement_type", native_enum=False), default=MovementType.AJUSTE, index=True
    )

    inventory: Mapped["Stock"] = relationship(back_populates="movements")

    @property
    def variant_id(self) -> int:
        return self.inventory.variant_id