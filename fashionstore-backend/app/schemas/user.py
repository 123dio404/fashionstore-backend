from pydantic import BaseModel, Field
from app.models.user import Role
from app.schemas.common import ORMModel

class UserCreate(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    full_name: str = Field(min_length=2, max_length=150)
    password: str = Field(min_length=8, max_length=128)
    role: Role = Role.CLIENTE
    is_active: bool = True

class UserUpdate(BaseModel):
    email: str | None = Field(default=None, min_length=5, max_length=320)
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: Role | None = None
    is_active: bool | None = None


class ProfileUpdate(BaseModel):
    email: str | None = Field(default=None, min_length=5, max_length=320)
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    password: str | None = Field(default=None, min_length=8, max_length=128)

class UserResponse(ORMModel):
    id: int
    email: str
    full_name: str
    role: Role | None
    is_active: bool