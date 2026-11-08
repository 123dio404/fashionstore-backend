import re
from datetime import datetime, timedelta, timezone
from typing import Any
import bcrypt
from jose import JWTError, jwt
from app.core.config import settings

def _password_bytes(password: str) -> bytes:
    value = password.encode('utf-8')
    if len(value) > 72:
        raise ValueError('Password must be at most 72 UTF-8 bytes for bcrypt')
    return value

def validate_password_complexity(password: str) -> str:
    """Verifica que la contraseña cumpla los requisitos de seguridad:
    - Al menos 8 caracteres (máximo 72)
    - Al menos 1 letra mayúscula
    - Al menos 1 letra minúscula
    - Al menos 1 número
    - Al menos 1 carácter especial
    """
    if len(password) < 8:
        raise ValueError('La contraseña debe tener al menos 8 caracteres.')
    if len(password.encode('utf-8')) > 72:
        raise ValueError('La contraseña no debe superar los 72 caracteres.')
    if not re.search(r'[A-Z]', password):
        raise ValueError('La contraseña debe contener al menos una letra mayúscula (A-Z).')
    if not re.search(r'[a-z]', password):
        raise ValueError('La contraseña debe contener al menos una letra minúscula (a-z).')
    if not re.search(r'[0-9]', password):
        raise ValueError('La contraseña debe contener al menos un número (0-9).')
    if not re.search(r'[!@#$%^&*(),.?":{}|<>\-_+=\[\]\\/~`\';]', password):
        raise ValueError('La contraseña debe contener al menos un carácter especial (!@#$%^&*...).')
    return password

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try: return bcrypt.checkpw(_password_bytes(plain_password), hashed_password.encode('utf-8'))
    except (ValueError, TypeError): return False

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode('utf-8')

def create_access_token(subject: str | int, expires_delta: timedelta | None = None, claims: dict[str, Any] | None = None) -> str:
    expires = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    payload: dict[str, Any] = {'sub': str(subject), 'exp': expires}
    if claims: payload.update(claims)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])

def create_password_reset_token(user_id: int, email: str, expires_minutes: int = 30) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {
        'sub': str(user_id),
        'email': email,
        'purpose': 'password_reset',
        'exp': expires,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

def decode_password_reset_token(token: str) -> dict[str, Any]:
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    if payload.get('purpose') != 'password_reset':
        raise JWTError('Token inválido para restablecimiento de contraseña')
    return payload

__all__ = [
    'JWTError',
    'create_access_token',
    'decode_access_token',
    'create_password_reset_token',
    'decode_password_reset_token',
    'get_password_hash',
    'validate_password_complexity',
    'verify_password',
]
