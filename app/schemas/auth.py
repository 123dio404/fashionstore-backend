from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.core.security import validate_password_complexity
from app.models.user import Role
from app.schemas.common import ORMModel

class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    full_name: str = Field(min_length=2, max_length=150)
    password: str = Field(min_length=8, max_length=72)

    @field_validator('password')
    @classmethod
    def check_password_complexity(cls, v: str) -> str:
        return validate_password_complexity(v)

class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=72)
    confirm_password: str = Field(min_length=8, max_length=72)

    @field_validator('new_password')
    @classmethod
    def check_new_password_complexity(cls, v: str) -> str:
        return validate_password_complexity(v)

class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)

class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10)
    new_password: str = Field(min_length=8, max_length=72)
    confirm_password: str = Field(min_length=8, max_length=72)

    @field_validator('new_password')
    @classmethod
    def check_reset_password_complexity(cls, v: str) -> str:
        return validate_password_complexity(v)

class MessageResponse(BaseModel):
    detail: str
    reset_link: str | None = None
    email_sent: bool = False

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    user: 'UserResponse'

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'

class UserResponse(ORMModel):
    id: int
    tenant_id: int | None = None
    tenant_name: str | None = None
    plan_name: str | None = None
    email: str
    full_name: str
    role: Role | None
    is_active: bool

LoginResponse.model_rebuild()