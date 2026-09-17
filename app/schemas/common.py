from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar('T')

class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class Message(BaseModel):
    detail: str

class Page(ORMModel, Generic[T]):
    items: list[T]
    total: int

class IDModel(ORMModel):
    id: UUID
    created_at: datetime | None = None
