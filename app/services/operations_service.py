from datetime import date, datetime, time, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.operations import (
    Facility,
    FacilityReservation,
    FacilityReservationStatus,
    MaintenanceTask,
    Priority,
    TaskStatus,
)
from app.models.user import User
from app.schemas.operations import (
    AvailabilityResponse,
    FacilityCreate,
    FacilityReservationCreate,
    FacilityReservationUpdate,
    FacilityUpdate,
    FacilityUsageItem,
    FacilityUsageResponse,
    MaintenanceCreate,
    MaintenanceUpdate,
    TimeSlot,
)

ACTIVE_STATUSES = (FacilityReservationStatus.PENDIENTE, FacilityReservationStatus.CONFIRMADA, FacilityReservationStatus.COMPLETADA)


def get_facility(db: Session, facility_id: int) -> Facility:
    facility = db.get(Facility, facility_id)
    if facility is None:
        raise HTTPException(404, "Facility not found")
    return facility


def list_facilities(db: Session, active_only: bool = False) -> list[Facility]:
    q = select(Facility).order_by(Facility.name)
    if active_only:
        q = q.where(Facility.is_active.is_(True))
    return list(db.scalars(q).all())


def create_facility(db: Session, data: FacilityCreate, user_id: int) -> Facility:
    facility = Facility(**data.model_dump(), created_by_id=user_id)
    db.add(facility)
    try:
        db.commit()
        db.refresh(facility)
        return facility
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Facility name already exists")


def update_facility(db: Session, facility_id: int, data: FacilityUpdate) -> Facility:
    facility = get_facility(db, facility_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(facility, k, v)
    try:
        db.commit()
        db.refresh(facility)
        return facility
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Facility name already exists")


def delete_facility(db: Session, facility_id: int) -> None:
    facility = get_facility(db, facility_id)
    db.delete(facility)
    db.commit()


def _slot_times(open_time: time | None, close_time: time | None) -> list[tuple[time, time]]:
    start = datetime.combine(date.min, open_time or time(9, 0))
    end = datetime.combine(date.min, close_time or time(21, 0))
    cursor = start
    slots: list[tuple[time, time]] = []
    while cursor < end:
        nxt = min(cursor + timedelta(minutes=30), end)
        slots.append((cursor.time(), nxt.time()))
        cursor = nxt
    return slots


def _overlaps(start: time, end: time, r: FacilityReservation) -> bool:
    return r.start_time < end and r.end_time > start


def check_availability(db: Session, facility_id: int, day: date) -> AvailabilityResponse:
    facility = get_facility(db, facility_id)
    reservations = list(
        db.scalars(
            select(FacilityReservation).where(
                FacilityReservation.facility_id == facility_id,
                FacilityReservation.date == day,
                FacilityReservation.status.in_(ACTIVE_STATUSES),
            )
        ).all()
    )
    slots: list[TimeSlot] = []
    for start, end in _slot_times(facility.open_time, facility.close_time):
        booked = sum(1 for r in reservations if _overlaps(start, end, r))
        if not facility.is_active:
            slots.append(TimeSlot(start_time=start, end_time=end, available=False, reason="Instalación inactiva"))
        elif booked >= facility.capacity:
            slots.append(TimeSlot(start_time=start, end_time=end, available=False, reason="Capacidad completa"))
        else:
            slots.append(TimeSlot(start_time=start, end_time=end, available=True))
    booked = sum(1 for r in reservations if _overlaps(slots[0].start_time, slots[-1].end_time, r)) if slots else 0
    return AvailabilityResponse(
        facility_id=facility.id,
        facility_name=facility.name,
        date=day,
        open_time=facility.open_time,
        close_time=facility.close_time,
        booked=booked,
        capacity=facility.capacity,
        slots=slots,
    )


def create_reservation(db: Session, data: FacilityReservationCreate, user_id: int) -> FacilityReservation:
    facility = get_facility(db, data.facility_id)
    if not facility.is_active:
        raise HTTPException(400, "Facility is not active")
    if data.end_time <= data.start_time:
        raise HTTPException(400, "end_time must be after start_time")
    if facility.open_time is not None and facility.close_time is not None:
        if data.start_time < facility.open_time or data.end_time > facility.close_time:
            raise HTTPException(400, "Reservation outside opening hours")
    existing = list(
        db.scalars(
            select(FacilityReservation).where(
                FacilityReservation.facility_id == data.facility_id,
                FacilityReservation.date == data.date,
                FacilityReservation.status.in_(ACTIVE_STATUSES),
            )
        ).all()
    )
    booked = sum(1 for r in existing if _overlaps(data.start_time, data.end_time, r))
    if booked >= facility.capacity:
        raise HTTPException(409, "No availability for the requested slot")
    reservation = FacilityReservation(
        facility_id=data.facility_id,
        user_id=user_id,
        date=data.date,
        start_time=data.start_time,
        end_time=data.end_time,
        status=FacilityReservationStatus.CONFIRMADA,
        notes=data.notes,
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    return reservation


def get_reservation(db: Session, reservation_id: int) -> FacilityReservation:
    reservation = db.get(FacilityReservation, reservation_id)
    if reservation is None:
        raise HTTPException(404, "Reservation not found")
    return reservation


def list_reservations(
    db: Session,
    facility_id: int | None = None,
    day: date | None = None,
    user_id: int | None = None,
) -> list[FacilityReservation]:
    q = select(FacilityReservation).order_by(FacilityReservation.date.desc(), FacilityReservation.start_time)
    if facility_id is not None:
        q = q.where(FacilityReservation.facility_id == facility_id)
    if day is not None:
        q = q.where(FacilityReservation.date == day)
    if user_id is not None:
        q = q.where(FacilityReservation.user_id == user_id)
    return list(db.scalars(q).all())


def update_reservation(db: Session, reservation_id: int, data: FacilityReservationUpdate) -> FacilityReservation:
    reservation = get_reservation(db, reservation_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(reservation, k, v)
    db.commit()
    db.refresh(reservation)
    return reservation


def delete_reservation(db: Session, reservation_id: int) -> None:
    reservation = get_reservation(db, reservation_id)
    db.delete(reservation)
    db.commit()


def get_task(db: Session, task_id: int) -> MaintenanceTask:
    task = db.get(MaintenanceTask, task_id)
    if task is None:
        raise HTTPException(404, "Maintenance task not found")
    return task


def create_task(db: Session, data: MaintenanceCreate, user_id: int) -> MaintenanceTask:
    if data.facility_id is not None and db.get(Facility, data.facility_id) is None:
        raise HTTPException(404, "Facility not found")
    if data.assignee_id is not None and db.get(User, data.assignee_id) is None:
        raise HTTPException(404, "Assignee user not found")
    task = MaintenanceTask(**data.model_dump(), created_by_id=user_id)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def list_tasks(
    db: Session,
    status: TaskStatus | None = None,
    priority: Priority | None = None,
    facility_id: int | None = None,
    assignee_id: int | None = None,
) -> list[MaintenanceTask]:
    q = select(MaintenanceTask).order_by(MaintenanceTask.scheduled_date.asc().nulls_last(), MaintenanceTask.created_at.desc())
    if status is not None:
        q = q.where(MaintenanceTask.status == status)
    if priority is not None:
        q = q.where(MaintenanceTask.priority == priority)
    if facility_id is not None:
        q = q.where(MaintenanceTask.facility_id == facility_id)
    if assignee_id is not None:
        q = q.where(MaintenanceTask.assignee_id == assignee_id)
    return list(db.scalars(q).all())


def update_task(db: Session, task_id: int, data: MaintenanceUpdate) -> MaintenanceTask:
    task = get_task(db, task_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(task, k, v)
    if task.status == TaskStatus.COMPLETADA and task.completed_at is None:
        task.completed_at = datetime.now(timezone.utc)
    if task.status != TaskStatus.COMPLETADA:
        task.completed_at = None
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, task_id: int) -> None:
    task = get_task(db, task_id)
    db.delete(task)
    db.commit()


def _period_bounds(period: str) -> tuple[date, date]:
    year, month = int(period[:4]), int(period[5:7])
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end


def facility_usage_report(db: Session, period: str) -> FacilityUsageResponse:
    start, end = _period_bounds(period)
    reservations = list(
        db.scalars(
            select(FacilityReservation).where(FacilityReservation.date >= start, FacilityReservation.date < end)
        ).all()
    )
    facilities = {f.id: f for f in list_facilities(db)}

    by_facility: dict[int, list[FacilityReservation]] = {}
    for r in reservations:
        by_facility.setdefault(r.facility_id, []).append(r)

    items: list[FacilityUsageItem] = []
    for facility_id, rs in sorted(by_facility.items(), key=lambda kv: kv[1], reverse=False):
        facility = facilities.get(facility_id)
        total = len(rs)
        completed = sum(1 for r in rs if r.status == FacilityReservationStatus.COMPLETADA)
        cancelled = sum(1 for r in rs if r.status == FacilityReservationStatus.CANCELADA)
        total_hours = sum(
            (datetime.combine(r.date, r.end_time) - datetime.combine(r.date, r.start_time)).seconds / 3600
            for r in rs
            if r.status != FacilityReservationStatus.CANCELADA
        )
        open_time = facility.open_time if facility else None
        close_time = facility.close_time if facility else None
        hours_per_day = (
            (datetime.combine(date.min, close_time or time(21, 0)) - datetime.combine(date.min, open_time or time(9, 0))).seconds / 3600
        )
        days_in_period = (end - start).days
        available_hours = (facility.capacity if facility else 0) * hours_per_day * days_in_period
        occupancy = round(min(total_hours / available_hours, 1.0) * 100, 2) if available_hours else 0.0
        items.append(
            FacilityUsageItem(
                facility_id=facility_id,
                facility_name=facility.name if facility else "Eliminada",
                reservations_count=total,
                completed_count=completed,
                cancelled_count=cancelled,
                total_hours=round(total_hours, 2),
                capacity=facility.capacity if facility else 0,
                occupancy_rate=occupancy,
            )
        )
    items.sort(key=lambda i: i.total_hours, reverse=True)
    return FacilityUsageResponse(period=period, total_reservations=len(reservations), items=items)