from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ContactFormCreateCmd(BaseModel):
    """Cuerpo del formulario (campos en camelCase como en el front)."""

    model_config = ConfigDict(str_strip_whitespace=True, populate_by_name=True)

    full_name: str = Field(..., min_length=1, max_length=200, validation_alias="fullName")
    email: str = Field(..., min_length=3, max_length=255)
    affiliation: str = Field(..., min_length=1, max_length=500)
    profile: str = Field(..., min_length=1, max_length=200)
    interest: str = Field(..., min_length=1, max_length=500)
    message: str = Field(..., min_length=1, max_length=10000)
    locale: str = Field(..., min_length=2, max_length=10)
    source: str = Field(..., min_length=1, max_length=100)
    submitted_at: Optional[datetime] = Field(default=None, validation_alias="submittedAt")


class ContactFormReadDTO(BaseModel):
    id: UUID
    full_name: str = Field(serialization_alias="fullName")
    email: str
    affiliation: str
    profile: str
    interest: str
    message: str
    locale: str
    source: str
    submitted_at: datetime = Field(serialization_alias="submittedAt")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ContactFormListPage(BaseModel):
    items: list[ContactFormReadDTO]
    total: int
    skip: int
    limit: int
    has_next: bool
    has_previous: bool
