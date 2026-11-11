from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.core.security import get_password_hash, verify_password
from app.models.user import Role, Rol, User
from app.schemas.auth import RegisterRequest
from app.schemas.user import UserCreate


def normalize_email(email: str) -> str: return email.strip().lower()


def get_role(db: Session, role: Role | str) -> Rol:
    nombre = role.value if isinstance(role, Role) else str(role)
    rol = db.scalar(select(Rol).where(Rol.nombre == nombre))
    if rol is None:
        rol = Rol(nombre=nombre)
        db.add(rol)
        db.flush()
    return rol


def register_user(db: Session, data: RegisterRequest) -> User:
    email = normalize_email(data.email)
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Email already registered')
    user = User(email=email, full_name=data.full_name.strip(), password_hash=get_password_hash(data.password))
    user.roles = [get_role(db, Role.CLIENTE)]
    db.add(user)
    try: db.commit(); db.refresh(user)
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail='Email already registered')
    return user


def create_user(db: Session, data: UserCreate, tenant_id: int | None = None) -> User:
    email = normalize_email(data.email)
    if db.scalar(select(User).where(User.email == email)): raise HTTPException(status_code=409, detail='Email already registered')
    user = User(
        email=email,
        full_name=data.full_name.strip(),
        password_hash=get_password_hash(data.password),
        is_active=data.is_active,
        tenant_id=tenant_id,
    )
    user.roles = [get_role(db, data.role)]
    db.add(user)
    try: db.commit(); db.refresh(user)
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail='Email already registered')
    return user


def set_user_role(db: Session, user: User, role: Role) -> User:
    user.roles = [get_role(db, role)]
    db.add(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None or not user.is_active or not verify_password(password, user.password_hash): return None
    return user


def change_user_password(
    db: Session,
    user: User,
    current_password: str,
    new_password: str,
    confirm_password: str,
) -> None:
    """Permite al usuario autenticado cambiar su contraseña."""
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual es incorrecta.",
        )
    if new_password != confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contraseña y su confirmación no coinciden.",
        )
    if current_password == new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contraseña no puede ser idéntica a la contraseña actual.",
        )

    user.password_hash = get_password_hash(new_password)
    db.commit()


def request_password_reset(db: Session, email: str) -> dict:
    """Inicia el proceso de recuperación de contraseña y envía el correo."""
    from app.core.security import create_password_reset_token
    from app.services.email_service import send_password_reset_email

    normalized = normalize_email(email)
    user = db.scalar(select(User).where(User.email == normalized))

    if not user or not user.is_active:
        # Por seguridad no revelamos si el correo existe o no a atacantes,
        # pero devolvemos una respuesta exitosa uniforme.
        return {
            "detail": "Si el correo está registrado, recibirás un enlace de recuperación en los próximos minutos.",
            "reset_link": None,
            "email_sent": False,
        }

    token = create_password_reset_token(user_id=user.id, email=user.email)
    result = send_password_reset_email(to_email=user.email, full_name=user.full_name, token=token)

    return {
        "detail": "Hemos enviado las instrucciones para restablecer tu contraseña a tu correo electrónico.",
        "reset_link": result.get("reset_url"),
        "email_sent": result.get("sent", False),
    }


def reset_password_with_token(
    db: Session,
    token: str,
    new_password: str,
    confirm_password: str,
) -> None:
    """Restablece la contraseña de un usuario mediante el token firmado recibido por correo."""
    from jose import JWTError
    from app.core.security import decode_password_reset_token

    if new_password != confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contraseña y su confirmación no coinciden.",
        )

    try:
        payload = decode_password_reset_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace de recuperación es inválido o ha expirado. Por favor, solicita uno nuevo.",
        )

    user_id = int(payload.get("sub", 0))
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado o inactivo.",
        )

    user.password_hash = get_password_hash(new_password)
    db.commit()
