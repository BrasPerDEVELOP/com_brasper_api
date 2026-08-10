# app/modules/transactions/application/schemas/tag_schema.py
"""Schemas del catálogo de etiquetas de transacción."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.transactions.domain.models import Tag


# Paleta cerrada: el front pinta cada clave con su trío de colores. Se valida
# aquí para que no entren valores sueltos que la UI no sepa dibujar.
TAG_COLORS: tuple[str, ...] = (
    "amber",
    "blue",
    "purple",
    "rose",
    "green",
    "cyan",
    "orange",
    "slate",
)


def _normalize_color(value: Optional[str]) -> str:
    candidate = (value or "").strip().lower()
    return candidate if candidate in TAG_COLORS else "slate"


class TagCreateCmd(BaseModel):
    label: str = Field(min_length=1, max_length=60)
    color: str = "slate"
    active: bool = True
    counts_as_new_client: bool = False
    position: int = 0

    @field_validator("label")
    @classmethod
    def _strip_label(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("El nombre de la etiqueta no puede estar vacío")
        return cleaned

    @field_validator("color")
    @classmethod
    def _valid_color(cls, v: str) -> str:
        return _normalize_color(v)


class TagUpdateCmd(BaseModel):
    id: UUID
    label: Optional[str] = Field(default=None, max_length=60)
    color: Optional[str] = None
    active: Optional[bool] = None
    counts_as_new_client: Optional[bool] = None
    position: Optional[int] = None

    @field_validator("label")
    @classmethod
    def _strip_label(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("El nombre de la etiqueta no puede estar vacío")
        return cleaned

    @field_validator("color")
    @classmethod
    def _valid_color(cls, v: Optional[str]) -> Optional[str]:
        return None if v is None else _normalize_color(v)


class TagReadDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    label: str
    color: str
    active: bool
    counts_as_new_client: bool
    position: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_tag(cls, entity: Tag) -> "TagReadDTO":
        return cls(
            id=entity.id,
            label=entity.label,
            color=entity.color,
            active=entity.active,
            counts_as_new_client=entity.counts_as_new_client,
            position=entity.position,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
