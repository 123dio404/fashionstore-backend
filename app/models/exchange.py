from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.branch import Branch
    from app.models.commerce import Sale
    from app.models.inventory import Stock
    from app.models.tenant import Tenant
    from app.models.user import User


class GarmentExchange(Base):
    """
    Registro formal de cambios de prendas de vestir (Postventa).
    Permite cambiar una prenda por otra (talla/modelo), validando el plazo máximo
    permitido (30 días), actualizando stock y calculando la diferencia económica.
    """
    __tablename__ = "cambio_prenda"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column("id_empresa", ForeignKey("empresa.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[int] = mapped_column("id_sucursal", ForeignKey("sucursal.id", ondelete="RESTRICT"), index=True)
    original_sale_id: Mapped[int] = mapped_column("id_venta_origen", ForeignKey("venta.id", ondelete="RESTRICT"), index=True)
    returned_stock_id: Mapped[int] = mapped_column("id_inventario_devuelto", ForeignKey("inventario.id", ondelete="RESTRICT"))
    new_stock_id: Mapped[int] = mapped_column("id_inventario_nuevo", ForeignKey("inventario.id", ondelete="RESTRICT"))
    quantity: Mapped[int] = mapped_column("cantidad", Integer, default=1, nullable=False)
    price_difference: Mapped[Decimal] = mapped_column("diferencia_precio", Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    reason: Mapped[str] = mapped_column("motivo", String(255), default="Cambio de talla / modelo")
    user_id: Mapped[int | None] = mapped_column("id_usuario", ForeignKey("usuario.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column("fecha", DateTime(timezone=True), server_default=func.now(), nullable=False)

    tenant: Mapped["Tenant"] = relationship()
    branch: Mapped["Branch"] = relationship()
    original_sale: Mapped["Sale"] = relationship()
    returned_stock: Mapped["Stock"] = relationship(foreign_keys=[returned_stock_id])
    new_stock: Mapped["Stock"] = relationship(foreign_keys=[new_stock_id])
    user: Mapped["User | None"] = relationship()
