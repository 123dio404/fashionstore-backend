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

__all__=['JWTError','create_access_token','decode_access_token','get_password_hash','verify_password']
