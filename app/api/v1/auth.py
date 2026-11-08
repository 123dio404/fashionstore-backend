from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginResponse,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
)
from app.schemas.user import UserResponse
from app.services.auth_service import (
    authenticate_user,
    change_user_password,
    register_user,
    request_password_reset,
    reset_password_with_token,
)

router = APIRouter(prefix='/auth', tags=['auth'])

@router.post('/register', response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    return register_user(db, data)

@router.post('/login', response_model=LoginResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form.username, form.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Credenciales incorrectas o usuario inactivo',
            headers={'WWW-Authenticate': 'Bearer'},
        )
    role_val = user.role.value if user.role else 'Cliente'
    claims = {
        'role': role_val,
        'tenant_id': user.tenant_id,
        'tenant_name': user.tenant_name,
    }
    return {'access_token': create_access_token(user.id, claims=claims), 'token_type': 'bearer', 'user': user}

@router.post('/change-password', response_model=MessageResponse)
def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Permite al usuario autenticado cambiar su propia contraseña."""
    change_user_password(
        db,
        current_user,
        current_password=data.current_password,
        new_password=data.new_password,
        confirm_password=data.confirm_password,
    )
    return MessageResponse(detail="Contraseña actualizada exitosamente.")

@router.post('/forgot-password', response_model=MessageResponse)
def forgot_password(
    data: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    """Genera token de recuperación y envía correo electrónico."""
    res = request_password_reset(db, data.email)
    return MessageResponse(
        detail=res["detail"],
        reset_link=res.get("reset_link"),
        email_sent=res.get("email_sent", False),
    )

@router.post('/reset-password', response_model=MessageResponse)
def reset_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """Valida token y aplica la nueva contraseña."""
    reset_password_with_token(
        db,
        token=data.token,
        new_password=data.new_password,
        confirm_password=data.confirm_password,
    )
    return MessageResponse(detail="Contraseña restablecida exitosamente. Ya puedes iniciar sesión.")

