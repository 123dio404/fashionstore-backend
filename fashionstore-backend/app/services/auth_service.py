from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.core.security import get_password_hash, verify_password
from app.models.user import Role, User
from app.schemas.auth import RegisterRequest
from app.schemas.user import UserCreate

def normalize_email(email: str) -> str: return email.strip().lower()

def register_user(db: Session, data: RegisterRequest) -> User:
    email = normalize_email(data.email)
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Email already registered')
    user = User(email=email, full_name=data.full_name.strip(), password_hash=get_password_hash(data.password), role=Role.CLIENTE)
    db.add(user)
    try: db.commit(); db.refresh(user)
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail='Email already registered')
    return user

def create_user(db: Session, data: UserCreate) -> User:
    email = normalize_email(data.email)
    if db.scalar(select(User).where(User.email == email)): raise HTTPException(status_code=409, detail='Email already registered')
    user = User(email=email, full_name=data.full_name.strip(), password_hash=get_password_hash(data.password), role=data.role, is_active=data.is_active)
    db.add(user)
    try: db.commit(); db.refresh(user)
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail='Email already registered')
    return user

def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None or not user.is_active or not verify_password(password, user.password_hash): return None
    return user
