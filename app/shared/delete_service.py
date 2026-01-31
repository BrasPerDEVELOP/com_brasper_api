from typing import Protocol, TypeVar, Generic, Type
from uuid import UUID
from pydantic import BaseModel

T = TypeVar("T")

class DeleteResponse(BaseModel):
    """Respuesta estándar para operaciones de eliminación."""
    status: bool
    deleted_id: str | None = None
