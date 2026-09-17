from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.product import Product


class Supplier(Base):
    __tablename__ = "proveedor"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column("nombre", String(150), index=True)
    ci: Mapped[str] = mapped_column("ci", String(30), unique=True)
    phone: Mapped[str | None] = mapped_column("telefono", String(20), nullable=True)
    email: Mapped[str | None] = mapped_column("email", String(150), nullable=True)
    address: Mapped[str | None] = mapped_column("direccion", String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column("estado", Boolean, default=True, nullable=False)

    products: Mapped[list["Product"]] = relationship(secondary="producto_proveedor", back_populates="suppliers")


class ProductSupplier(Base):
    __tablename__ = "producto_proveedor"

    product_id: Mapped[int] = mapped_column("id_producto", ForeignKey("producto.id", ondelete="CASCADE"), primary_key=True)
    supplier_id: Mapped[int] = mapped_column("id_proveedor", ForeignKey("proveedor.id", ondelete="RESTRICT"), primary_key=True)
    purchase_price: Mapped[Decimal] = mapped_column("precio_compra", Numeric(12, 2))