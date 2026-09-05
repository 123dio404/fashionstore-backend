from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db, require_role
from app.core.security import get_password_hash
from app.models.user import Role, User
from app.schemas.user import ProfileUpdate, UserCreate, UserResponse, UserUpdate
from app.services.auth_service import create_user, normalize_email
router = APIRouter(prefix='/users', tags=['users'])
admin = Depends(require_role(Role.ADMINISTRADOR))

@router.get('/me', response_model=UserResponse)
def me(current: User = Depends(get_current_user)): return current


@router.put('/me', response_model=UserResponse)
def update_me(
    data: ProfileUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    values = data.model_dump(exclude_unset=True)
    if 'email' in values:
        values['email'] = normalize_email(values['email'])
    if 'password' in values:
        values['password_hash'] = get_password_hash(values.pop('password'))
    for key, value in values.items():
        setattr(current, key, value)
    try:
        db.commit()
        db.refresh(current)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Email already registered')
    return current


@router.get('', response_model=list[UserResponse], dependencies=[admin])
def list_users(db: Session = Depends(get_db)): return list(db.scalars(select(User).order_by(User.created_at)).all())
@router.post('', response_model=UserResponse, status_code=201, dependencies=[admin])
def add_user(data: UserCreate, db: Session = Depends(get_db)): return create_user(db, data)
@router.get('/{user_id}', response_model=UserResponse, dependencies=[admin])
def get_user(user_id: UUID, db: Session = Depends(get_db)):
    obj = db.get(User, user_id)
    if obj is None: raise HTTPException(404, 'User not found')
    return obj
@router.patch('/{user_id}', response_model=UserResponse, dependencies=[admin])
@router.put('/{user_id}', response_model=UserResponse, include_in_schema=False, dependencies=[admin])
def edit_user(user_id: UUID, data: UserUpdate, db: Session = Depends(get_db)):
    obj = db.get(User, user_id)
    if obj is None: raise HTTPException(404, 'User not found')
    values = data.model_dump(exclude_unset=True)
    if 'email' in values: values['email'] = normalize_email(values['email'])
    if 'password' in values: values['password_hash'] = get_password_hash(values.pop('password'))
    for key, value in values.items(): setattr(obj, key, value)
    try: db.commit(); db.refresh(obj)
    except IntegrityError: db.rollback(); raise HTTPException(409, 'Email already registered')
    return obj
@router.delete('/{user_id}', status_code=204, dependencies=[admin])
def remove_user(user_id: UUID, db: Session = Depends(get_db)):
    obj = db.get(User, user_id)
    if obj is None: raise HTTPException(404, 'User not found')
    obj.is_active = False; db.commit()
