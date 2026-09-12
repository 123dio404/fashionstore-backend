import enum
from datetime import date, datetime, time
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Enum, ForeignKey, Integer, String, Text, Time, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class FacilityReservationStatus(str, enum.Enum):
    PENDIENTE = "pendiente"
    CONFIRMADA = "confirmada"
    CANCELADA = "cancelada"
    COMPLETADA = "completada"


class Priority(str, enum.Enum):
    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"
    CRITICA = "critica"


class TaskStatus(str, enum.Enum):
    PENDIENTE = "pendiente"
    EN_PROGRESO = "en_progreso"
    COMPLETADA = "completada"
    CANCELADA = "cancelada"


class Facility(Base):
    __tablename__ = "facilities"
    __table_args__ = (CheckConstraint("capacity > 0", name="ck_facility_capacity_positive"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(150), nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    open_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    close_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    created_by: Mapped["User"] = relationship()
    reservations: Mapped[list["FacilityReservation"]] = relationship(
        back_populates="facility", cascade="all, delete-orphan"
    )
    maintenance_tasks: Mapped[list["MaintenanceTask"]] = relationship(back_populates="facility")


class FacilityReservation(Base):
    __tablename__ = "facility_reservations"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="ck_reservation_time_range"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    facility_id: Mapped[UUID] = mapped_column(
        ForeignKey("facilities.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    status: Mapped[FacilityReservationStatus] = mapped_column(
        Enum(FacilityReservationStatus, name="reservation_status", native_enum=False),
        default=FacilityReservationStatus.PENDIENTE,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    facility: Mapped["Facility"] = relationship(back_populates="reservations")
    user: Mapped["User"] = relationship()


class MaintenanceTask(Base):
    __tablename__ = "maintenance_tasks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    facility_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("facilities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assignee_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, name="priority", native_enum=False), default=Priority.MEDIA, index=True
    )
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status", native_enum=False),
        default=TaskStatus.PENDIENTE,
        index=True,
    )
    scheduled_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    facility: Mapped["Facility | None"] = relationship(back_populates="maintenance_tasks")
    assignee: Mapped["User | None"] = relationship(foreign_keys=[assignee_id])
    created_by: Mapped["User"] = relationship(foreign_keys=[created_by_id])