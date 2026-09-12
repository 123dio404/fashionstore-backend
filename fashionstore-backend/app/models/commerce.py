from datetime import date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.branch import Branch
    from app.models.inventory import Stock
    from app.models.user import User


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), default="activo", nullable=False, index=True)

    user: Mapped["User"] = relationship()
    items: Mapped[list["CartItem"]] = relationship(back_populates="cart", cascade="all, delete-orphan")


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_cart_items_quantity"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    cart_id: Mapped[UUID] = mapped_column(ForeignKey("carts.id", ondelete="CASCADE"), index=True)
    stock_id: Mapped[UUID] = mapped_column(ForeignKey("stocks.id", ondelete="RESTRICT"))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    cart: Mapped["Cart"] = relationship(back_populates="items")
    stock: Mapped["Stock"] = relationship()


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    client_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    branch_id: Mapped[UUID] = mapped_column(ForeignKey("branches.id", ondelete="RESTRICT"))
    sale_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    sale_type: Mapped[str] = mapped_column(String(40), nullable=False)

    client: Mapped["User | None"] = relationship(foreign_keys=[client_id])
    handler: Mapped["User"] = relationship(foreign_keys=[user_id])
    branch: Mapped["Branch"] = relationship()
    items: Mapped[list["SaleItem"]] = relationship(back_populates="sale", cascade="all, delete-orphan")
    payments: Mapped[list["SalePayment"]] = relationship(back_populates="sale", cascade="all, delete-orphan")


class SaleItem(Base):
    __tablename__ = "sale_items"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_sale_items_quantity"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    sale_id: Mapped[UUID] = mapped_column(ForeignKey("sales.id", ondelete="CASCADE"), index=True)
    stock_id: Mapped[UUID] = mapped_column(ForeignKey("stocks.id", ondelete="RESTRICT"))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    sale: Mapped["Sale"] = relationship(back_populates="items")
    stock: Mapped["Stock"] = relationship()


class SalePayment(Base):
    __tablename__ = "payments"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    sale_id: Mapped[UUID] = mapped_column(
        "order_id", ForeignKey("sales.id", ondelete="CASCADE"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(150), nullable=True)

    sale: Mapped["Sale"] = relationship(back_populates="payments")


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    branch_id: Mapped[UUID] = mapped_column(ForeignKey("branches.id", ondelete="RESTRICT"))
    reservation_date: Mapped[date] = mapped_column(nullable=False, index=True)
    reservation_time: Mapped[time] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pendiente", nullable=False, index=True)

    client: Mapped["User"] = relationship()
    branch: Mapped["Branch"] = relationship()
    items: Mapped[list["ReservationItem"]] = relationship(
        back_populates="reservation", cascade="all, delete-orphan"
    )


class ReservationItem(Base):
    __tablename__ = "reservation_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    reservation_id: Mapped[UUID] = mapped_column(
        ForeignKey("reservations.id", ondelete="CASCADE"), index=True
    )
    stock_id: Mapped[UUID] = mapped_column(ForeignKey("stocks.id", ondelete="RESTRICT"))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    reservation: Mapped["Reservation"] = relationship(back_populates="items")
    stock: Mapped["Stock"] = relationship()