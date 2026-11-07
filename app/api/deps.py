from collections.abc import Callable, Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError
from app.core.database import SessionLocal
from app.core.security import decode_access_token
from app.models.user import Role, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/v1/auth/login')
oauth2_optional = OAuth2PasswordBearer(tokenUrl='/api/v1/auth/login', auto_error=False)

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

def get_current_tenant_id(current_user: User = Depends(get_current_user)) -> int | None:
    """Retorna el ID de la empresa a la que pertenece el usuario autenticado (o None si es Superadmin)."""
    return current_user.tenant_id


def get_optional_current_user(
    token: str | None = Depends(oauth2_optional),
    db: Session = Depends(get_db),
) -> User | None:
    """Usuario autenticado si viene un token válido; None para endpoints públicos.

    Permite que el catálogo sea público pero que, cuando un usuario de una
    empresa consulta, solo vea los datos de su propio tenant.
    """
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        subject = payload.get('sub')
        if not subject:
            return None
        user = db.get(User, int(subject))
    except (JWTError, ValueError, TypeError):
        return None
    if user is None or not user.is_active:
        return None
    return user

def require_tenant(current_user: User = Depends(get_current_user)) -> int:
    """Exige que el usuario pertenezca a un tenant específico para operaciones comerciales o administrativas."""
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operación requiere pertenecer a una empresa contratante (tenant)"
        )
    return current_user.tenant_id

def require_ai_plan(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Verifica que la empresa del usuario tenga contratado el Plan Profesional con IA habilitada."""
    from app.models.tenant import Subscription, Tenant
    if current_user.tenant_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario sin empresa asignada")
    sub = db.query(Subscription).filter(
        Subscription.tenant_id == current_user.tenant_id,
        Subscription.status == "Activa"
    ).first()
    if not sub or not sub.plan or not sub.plan.has_ai_reports:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Los reportes generativos mediante IA están reservados para empresas con Plan Profesional. Actualice su suscripción."
        )
    return sub


def get_optional_user(token: str | None = Depends(oauth2_scheme_optional), db: Session = Depends(get_db)) -> User | None:
    """Extrae el usuario autenticado si existe un token Bearer en la petición, sin lanzar error 401 si no lo hay."""
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        subject = payload.get('sub')
        if not subject:
            return None
        user_id = int(subject)
        user = db.get(User, user_id)
        if user and user.is_active:
            return user
    except Exception:
        return None
    return None
