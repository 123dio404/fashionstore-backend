from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db, require_role
from app.core.security import get_password_hash
from app.models.user import Role, User
from app.schemas.user import ProfileUpdate, UserCreate, UserResponse, UserUpdate
from app.services.auth_service import create_user, normalize_email, set_user_role
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


@router.get('', response_model=list[UserResponse])
def list_users(
    current: User = Depends(require_role(Role.ADMINISTRADOR)),
    db: Session = Depends(get_db),
):
    query = select(User).order_by(User.id.desc())
    # Aislamiento multitenant: un administrador solo ve usuarios de su empresa.
    if current.tenant_id is not None:
        query = query.where(User.tenant_id == current.tenant_id)
    return list(db.scalars(query).all())


@router.post('', response_model=UserResponse, status_code=201)
def add_user(
    data: UserCreate,
    current: User = Depends(require_role(Role.ADMINISTRADOR)),
    db: Session = Depends(get_db),
):
    return create_user(db, data, tenant_id=current.tenant_id)


@router.get('/{user_id}', response_model=UserResponse)
def get_user(
    user_id: int,
    current: User = Depends(require_role(Role.ADMINISTRADOR)),
    db: Session = Depends(get_db),
):
    return _tenant_user(db, user_id, current)


@router.patch('/{user_id}', response_model=UserResponse)
@router.put('/{user_id}', response_model=UserResponse, include_in_schema=False)
def edit_user(
    user_id: int,
    data: UserUpdate,
    current: User = Depends(require_role(Role.ADMINISTRADOR)),
    db: Session = Depends(get_db),
):
    obj = _tenant_user(db, user_id, current)
    values = data.model_dump(exclude_unset=True)
    if 'email' in values: values['email'] = normalize_email(values['email'])
    if 'password' in values: values['password_hash'] = get_password_hash(values.pop('password'))
    new_role = values.pop('role', None)
    for key, value in values.items(): setattr(obj, key, value)
    if new_role is not None: set_user_role(db, obj, new_role)
    try: db.commit(); db.refresh(obj)
    except IntegrityError: db.rollback(); raise HTTPException(409, 'Email already registered')
    return obj


@router.delete('/{user_id}', status_code=204)
def remove_user(
    user_id: int,
    current: User = Depends(require_role(Role.ADMINISTRADOR)),
    db: Session = Depends(get_db),
):
    obj = _tenant_user(db, user_id, current)
    obj.is_active = False; db.commit()


def _tenant_user(db: Session, user_id: int, current: User) -> User:
    """Busca un usuario validando que pertenezca al mismo tenant del administrador."""
    obj = db.get(User, user_id)
    if obj is None:
        raise HTTPException(404, 'User not found')
    if current.tenant_id is not None and obj.tenant_id != current.tenant_id:
        raise HTTPException(404, 'User not found')
    return obj
