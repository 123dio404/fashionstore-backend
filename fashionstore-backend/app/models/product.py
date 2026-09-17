from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.inventory import Stock
    from app.models.supplier import Supplier


class Category(Base):
    __tablename__ = "categoria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column("nombre", String(100), unique=True, index=True)

    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Season(Base):
    __tablename__ = "temporada"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column("nombre", String(100), unique=True, index=True)
    start_date: Mapped[date] = mapped_column("fecha_inicio", Date)
    end_date: Mapped[date] = mapped_column("fecha_fin", Date)


class Size(Base):
    __tablename__ = "tallas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column("nombre", String(20), unique=True)


class Color(Base):
    __tablename__ = "color"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column("nombre", String(50), unique=True)


class Product(Base):
    __tablename__ = "producto"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column("id_categoria", ForeignKey("categoria.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column("nombre", String(150), index=True)
    brand: Mapped[str | None] = mapped_column("marca", String(100), nullable=True)
    price: Mapped[Decimal] = mapped_column("precio", Numeric(12, 2))
    is_active: Mapped[bool] = mapped_column("estado", Boolean, default=True, nullable=False)

    category: Mapped["Category"] = relationship(back_populates="products")
    suppliers: Mapped[list["Supplier"]] = relationship(secondary="producto_proveedor", back_populates="products")
    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class ProductVariant(Base):
    __tablename__ = "producto_variante"
    __table_args__ = (
        UniqueConstraint("id_producto", "id_talla", "id_color", name="uq_product_variant"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column("id_producto", ForeignKey("producto.id", ondelete="CASCADE"))
    codigo: Mapped[str] = mapped_column("codigo", String(50), unique=True)
    price: Mapped[Decimal] = mapped_column("precio", Numeric(12, 2))
    is_active: Mapped[bool] = mapped_column("estado", Boolean, default=True, nullable=False)
    size_id: Mapped[int | None] = mapped_column("id_talla", ForeignKey("tallas.id", ondelete="RESTRICT"), nullable=True)
    color_id: Mapped[int | None] = mapped_column("id_color", ForeignKey("color.id", ondelete="RESTRICT"), nullable=True)

    product: Mapped["Product"] = relationship(back_populates="variants")
    size: Mapped["Size | None"] = relationship()
    color: Mapped["Color | None"] = relationship()
    stocks: Mapped[list["Stock"]] = relationship(back_populates="variant")