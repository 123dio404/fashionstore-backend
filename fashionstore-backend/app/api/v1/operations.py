from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.models.operations import Priority, TaskStatus
from app.models.user import Role, User
from app.schemas.operations import (
    AvailabilityResponse,
    FacilityCreate,
    FacilityReservationCreate,
    FacilityReservationResponse,
    FacilityReservationUpdate,
    FacilityResponse,
    FacilityUpdate,
    FacilityUsageResponse,
    MaintenanceCreate,
    MaintenanceResponse,
    MaintenanceUpdate,
)
from app.services import operations_service

router = APIRouter(prefix='/operations', tags=['operations'])
manager = Depends(require_role(Role.ADMINISTRADOR, Role.ENCARGADO))

PRIVILEGED = (Role.ADMINISTRADOR, Role.ENCARGADO)


@router.get('/facilities', response_model=list[FacilityResponse])
def list_facilities(active_only: bool = False, db: Session = Depends(get_db)):
    return operations_service.list_facilities(db, active_only)


@router.post('/facilities', response_model=FacilityResponse, status_code=201, dependencies=[manager])
def create_facility(data: FacilityCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return operations_service.create_facility(db, data, user.id)


@router.get('/facilities/{facility_id}', response_model=FacilityResponse)
def get_facility(facility_id: UUID, db: Session = Depends(get_db)):
    return operations_service.get_facility(db, facility_id)


@router.patch('/facilities/{facility_id}', response_model=FacilityResponse, dependencies=[manager])
def update_facility(facility_id: UUID, data: FacilityUpdate, db: Session = Depends(get_db)):
    return operations_service.update_facility(db, facility_id, data)


@router.delete('/facilities/{facility_id}', status_code=204, dependencies=[manager])
def delete_facility(facility_id: UUID, db: Session = Depends(get_db)):
    operations_service.delete_facility(db, facility_id)


@router.get('/facilities/{facility_id}/availability', response_model=AvailabilityResponse)
def get_availability(facility_id: UUID, date: date, db: Session = Depends(get_db)):
    return operations_service.check_availability(db, facility_id, date)


@router.get('/reservations', response_model=list[FacilityReservationResponse])
def list_reservations(
    facility_id: UUID | None = None,
    day: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role in PRIVILEGED:
        return operations_service.list_reservations(db, facility_id, day)
    return operations_service.list_reservations(db, facility_id, day, user_id=user.id)


@router.post('/reservations', response_model=FacilityReservationResponse, status_code=201)
def create_reservation(
    data: FacilityReservationCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return operations_service.create_reservation(db, data, user.id)


@router.patch('/reservations/{reservation_id}', response_model=FacilityReservationResponse)
def update_reservation(
    reservation_id: UUID,
    data: FacilityReservationUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reservation = operations_service.get_reservation(db, reservation_id)
    if reservation.user_id != user.id and user.role not in PRIVILEGED:
        raise HTTPException(status_code=403, detail='Insufficient permissions')
    return operations_service.update_reservation(db, reservation_id, data)


@router.delete('/reservations/{reservation_id}', status_code=204)
def delete_reservation(
    reservation_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    reservation = operations_service.get_reservation(db, reservation_id)
    if reservation.user_id != user.id and user.role not in PRIVILEGED:
        raise HTTPException(status_code=403, detail='Insufficient permissions')
    operations_service.delete_reservation(db, reservation_id)


@router.get('/maintenance/tasks', response_model=list[MaintenanceResponse])
def list_tasks(
    status: TaskStatus | None = None,
    priority: Priority | None = None,
    facility_id: UUID | None = None,
    assignee_id: UUID | None = None,
    db: Session = Depends(get_db),
):
    return operations_service.list_tasks(db, status, priority, facility_id, assignee_id)


@router.post('/maintenance/tasks', response_model=MaintenanceResponse, status_code=201, dependencies=[manager])
def create_task(data: MaintenanceCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return operations_service.create_task(db, data, user.id)


@router.patch('/maintenance/tasks/{task_id}', response_model=MaintenanceResponse, dependencies=[manager])
def update_task(task_id: UUID, data: MaintenanceUpdate, db: Session = Depends(get_db)):
    return operations_service.update_task(db, task_id, data)


@router.delete('/maintenance/tasks/{task_id}', status_code=204, dependencies=[manager])
def delete_task(task_id: UUID, db: Session = Depends(get_db)):
    operations_service.delete_task(db, task_id)


@router.get('/reports/facility-usage', response_model=FacilityUsageResponse, dependencies=[manager])
def facility_usage_report(
    period: str = Query(..., pattern=r'^\d{4}-\d{2}$'),
    db: Session = Depends(get_db),
):
    return operations_service.facility_usage_report(db, period)