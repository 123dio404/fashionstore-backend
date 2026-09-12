from datetime import time
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.inventory import Stock
    from app.models.user import User


class City(Base):
    __tablename__ = "ciudad"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column("nombre", String(100), unique=True, index=True)

    branches: Mapped[list["Branch"]] = relationship(back_populates="city")


class Branch(Base):
    __tablename__ = "sucursal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    city_id: Mapped[int] = mapped_column("id_ciudad", ForeignKey("ciudad.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column("nombre", String(100))
    address: Mapped[str] = mapped_column("direccion", String(255))
    phone: Mapped[str | None] = mapped_column("telefono", String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column("estado", Boolean, default=True, nullable=False)

    city: Mapped["City"] = relationship(back_populates="branches")
    hours: Mapped[list["BranchHour"]] = relationship(back_populates="branch", cascade="all, delete-orphan")
    stocks: Mapped[list["Stock"]] = relationship(back_populates="branch")


class BranchHour(Base):
    __tablename__ = "horario_sucursal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    branch_id: Mapped[int] = mapped_column("id_sucursal", ForeignKey("sucursal.id", ondelete="CASCADE"), index=True)
    day_of_week: Mapped[str] = mapped_column("dia_semana", String(20))
    open_time: Mapped[time] = mapped_column("hora_inicio", Time)
    close_time: Mapped[time] = mapped_column("hora_fin", Time)

    branch: Mapped["Branch"] = relationship(back_populates="hours")
