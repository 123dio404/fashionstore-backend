from datetime import date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.branch import Branch
    from app.models.inventory import Stock
    from app.models.user import User


class Cart(Base):
    __tablename__ = "carrito"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column("id_usuario", ForeignKey("usuario.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column("fecha_creacion", DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column("fecha_actualizacion", DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    status: Mapped[str] = mapped_column("estado", String(30), default="Activo", nullable=False, index=True)

    items: Mapped[list["CartItem"]] = relationship(back_populates="cart", cascade="all, delete-orphan")


class CartItem(Base):
    __tablename__ = "carrito_detalle"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cart_id: Mapped[int] = mapped_column("id_carrito", ForeignKey("carrito.id", ondelete="CASCADE"), index=True)
    stock_id: Mapped[int] = mapped_column("id_inventario", ForeignKey("inventario.id", ondelete="RESTRICT"))
    quantity: Mapped[int] = mapped_column("cantidad", Integer, nullable=False)
    price: Mapped[Decimal] = mapped_column("precio", Numeric(12, 2), nullable=False)

    cart: Mapped["Cart"] = relationship(back_populates="items")
    stock: Mapped["Stock"] = relationship()


class Sale(Base):
    __tablename__ = "venta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column("id_cliente", ForeignKey("usuario.id", ondelete="RESTRICT"))
    user_id: Mapped[int | None] = mapped_column("id_usuario", ForeignKey("usuario.id", ondelete="SET NULL"), nullable=True)
    branch_id: Mapped[int] = mapped_column("id_sucursal", ForeignKey("sucursal.id", ondelete="RESTRICT"))
    sale_date: Mapped[datetime] = mapped_column("fecha", DateTime(timezone=True), server_default=func.now(), nullable=False)
    total: Mapped[Decimal] = mapped_column("total", Numeric(12, 2), nullable=False)
    sale_type: Mapped[str] = mapped_column("tipo_venta", String(30), nullable=False)

    branch: Mapped["Branch"] = relationship()
    items: Mapped[list["SaleItem"]] = relationship(back_populates="sale", cascade="all, delete-orphan")
    payments: Mapped[list["SalePayment"]] = relationship(back_populates="sale", cascade="all, delete-orphan")


class SaleItem(Base):
    __tablename__ = "detalle_venta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sale_id: Mapped[int] = mapped_column("id_venta", ForeignKey("venta.id", ondelete="CASCADE"), index=True)
    stock_id: Mapped[int] = mapped_column("id_inventario", ForeignKey("inventario.id", ondelete="RESTRICT"))
    quantity: Mapped[int] = mapped_column("cantidad", Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column("precio_unitario", Numeric(12, 2), nullable=False)

    sale: Mapped["Sale"] = relationship(back_populates="items")
    stock: Mapped["Stock"] = relationship()


class SalePayment(Base):
    __tablename__ = "pago"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sale_id: Mapped[int] = mapped_column("id_pedido", ForeignKey("venta.id", ondelete="CASCADE"), index=True)
    amount: Mapped[Decimal] = mapped_column("monto", Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column("estado", String(30), nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column("fecha_pago", DateTime(timezone=True), nullable=True)
    reference: Mapped[str | None] = mapped_column("referencia", String(100), nullable=True)

    sale: Mapped["Sale"] = relationship(back_populates="payments")


class Reservation(Base):
    __tablename__ = "reserva"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column("id_cliente", ForeignKey("usuario.id", ondelete="RESTRICT"), index=True)
    branch_id: Mapped[int] = mapped_column("id_sucursal", ForeignKey("sucursal.id", ondelete="RESTRICT"))
    reservation_date: Mapped[date] = mapped_column("fecha_reserva", nullable=False, index=True)
    reservation_time: Mapped[time] = mapped_column("hora_reserva", nullable=False)
    status: Mapped[str] = mapped_column("estado", String(30), default="Pendiente", nullable=False, index=True)

    branch: Mapped["Branch"] = relationship()
    items: Mapped[list["ReservationItem"]] = relationship(back_populates="reservation", cascade="all, delete-orphan")


class ReservationItem(Base):
    __tablename__ = "detalle_reserva"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reservation_id: Mapped[int] = mapped_column("id_reserva", ForeignKey("reserva.id", ondelete="CASCADE"), index=True)
    stock_id: Mapped[int] = mapped_column("id_inventario", ForeignKey("inventario.id", ondelete="RESTRICT"))
    quantity: Mapped[int] = mapped_column("cantidad", Integer, nullable=False)

    reservation: Mapped["Reservation"] = relationship(back_populates="items")
    stock: Mapped["Stock"] = relationship()