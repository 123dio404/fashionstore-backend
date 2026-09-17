from collections.abc import Callable, Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError
from app.core.database import SessionLocal
from app.core.security import decode_access_token
from app.models.user import Role, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/v1/auth/login')

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try: yield db
    finally: db.close()

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid authentication credentials', headers={'WWW-Authenticate': 'Bearer'})
    try:
        payload = decode_access_token(token)
        subject = payload.get('sub')
        if not subject: raise credentials_error
        user_id = int(subject)
    except (JWTError, ValueError, TypeError):
        raise credentials_error
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_error
    return user

def require_role(*roles: Role | str) -> Callable:
    allowed = {r.value if isinstance(r, Role) else str(r) for r in roles}
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        user_role = current_user.role
        if user_role is None or (user_role.value not in allowed and user_role not in allowed):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Insufficient permissions')
        return current_user
    return dependency