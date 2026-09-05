from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.user import Role
from app.schemas.common import ORMModel

class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    full_name: str = Field(min_length=2, max_length=150)
    password: str = Field(min_length=8, max_length=128)

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    user: 'UserResponse'

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'

class UserResponse(ORMModel):
    id: UUID
    email: str
    full_name: str
    role: Role
    is_active: bool

LoginResponse.model_rebuild()
