from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.core.security import create_access_token
from app.schemas.auth import LoginResponse, RegisterRequest
from app.schemas.user import UserResponse
from app.services.auth_service import authenticate_user, register_user

router = APIRouter(prefix='/auth', tags=['auth'])

@router.post('/register', response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    return register_user(db, data)

@router.post('/login', response_model=LoginResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form.username, form.password)
    role_val = user.role.value if user.role else 'Cliente'
    claims = {'role': role_val, 'tenant_id': user.tenant_id}
    return {'access_token': create_access_token(user.id, claims=claims), 'token_type': 'bearer', 'user': user}
