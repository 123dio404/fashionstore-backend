from datetime import date as DateType, datetime, time


from pydantic import BaseModel, Field

from app.models.operations import FacilityReservationStatus, Priority, TaskStatus
from app.schemas.common import ORMModel


class FacilityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    location: str | None = Field(default=None, max_length=150)
    capacity: int = Field(default=1, gt=0)
    is_active: bool = True
    open_time: time | None = None
    close_time: time | None = None


class FacilityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    location: str | None = Field(default=None, max_length=150)
    capacity: int | None = Field(default=None, gt=0)
    is_active: bool | None = None
    open_time: time | None = None
    close_time: time | None = None


class FacilityResponse(ORMModel):
    id: int
    name: str
    description: str | None
    location: str | None
    capacity: int
    is_active: bool
    open_time: time | None
    close_time: time | None
    created_by_id: int
    created_at: datetime
    updated_at: datetime


class TimeSlot(BaseModel):
    start_time: time
    end_time: time
    available: bool
    reason: str | None = None


class AvailabilityResponse(BaseModel):
    facility_id: int
    facility_name: str
    date: DateType
    open_time: time | None
    close_time: time | None
    booked: int
    capacity: int
    slots: list[TimeSlot]


class FacilityReservationCreate(BaseModel):
    facility_id: int
    date: DateType
    start_time: time
    end_time: time
    notes: str | None = None


class FacilityReservationUpdate(BaseModel):
    date: DateType | None = None
    start_time: time | None = None
    end_time: time | None = None
    status: FacilityReservationStatus | None = None
    notes: str | None = None


class FacilityReservationResponse(ORMModel):
    id: int
    facility_id: int
    user_id: int
    date: DateType
    start_time: time
    end_time: time
    status: FacilityReservationStatus
    notes: str | None
    created_at: datetime


class MaintenanceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    facility_id: int = None
    assignee_id: int = None
    priority: Priority = Priority.MEDIA
    status: TaskStatus = TaskStatus.PENDIENTE
    scheduled_date: DateType | None = None


class MaintenanceUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    facility_id: int = None
    assignee_id: int = None
    priority: Priority | None = None
    status: TaskStatus | None = None
    scheduled_date: DateType | None = None


class MaintenanceResponse(ORMModel):
    id: int
    title: str
    description: str | None
    facility_id: int | None
    assignee_id: int | None
    priority: Priority
    status: TaskStatus
    scheduled_date: DateType | None
    completed_at: datetime | None
    created_by_id: int
    created_at: datetime
    updated_at: datetime


class FacilityUsageItem(BaseModel):
    facility_id: int
    facility_name: str
    reservations_count: int
    completed_count: int
    cancelled_count: int
    total_hours: float
    capacity: int
    occupancy_rate: float


class FacilityUsageResponse(BaseModel):
    period: str
    total_reservations: int
    items: list[FacilityUsageItem]