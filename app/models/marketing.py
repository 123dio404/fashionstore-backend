from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, Table, Column, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.product import Product


collection_products = Table(
    "coleccion_producto", Base.metadata,
    Column("id_coleccion", Integer, ForeignKey("coleccion.id", ondelete="CASCADE"), primary_key=True),
    Column("id_producto", Integer, ForeignKey("producto.id", ondelete="CASCADE"), primary_key=True),
)
promotion_products = Table(
    "promocion_producto", Base.metadata,
    Column("id_promocion", Integer, ForeignKey("promocion.id", ondelete="CASCADE"), primary_key=True),
    Column("id_producto", Integer, ForeignKey("producto.id", ondelete="CASCADE"), primary_key=True),
)


class Collection(Base):
    __tablename__ = "coleccion"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column("nombre", String(150), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column("descripcion", Text, nullable=True)
    is_active: Mapped[bool] = mapped_column("estado", Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column("fecha_creacion", DateTime(timezone=True), server_default=func.now(), nullable=False)
    products: Mapped[list["Product"]] = relationship(secondary=collection_products)

    @property
    def product_ids(self): return [product.id for product in self.products]


class Promotion(Base):
    __tablename__ = "promocion"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column("nombre", String(150), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column("descripcion", Text, nullable=True)
    discount_type: Mapped[str] = mapped_column("tipo_descuento", String(20), nullable=False, default="percentage")
    discount_value: Mapped[Decimal] = mapped_column("valor_descuento", Numeric(12, 2), nullable=False)
    start_date: Mapped[date | None] = mapped_column("fecha_inicio", Date, nullable=True, index=True)
    end_date: Mapped[date | None] = mapped_column("fecha_fin", Date, nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column("estado", Boolean, default=True, nullable=False, index=True)
    products: Mapped[list["Product"]] = relationship(secondary=promotion_products)

    @property
    def product_ids(self): return [product.id for product in self.products]
