from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_ICONS = {"mdi:shield-check-outline", "mdi:account-heart-outline", "mdi:swap-horizontal-circle-outline", "mdi:clock-fast", "mdi:whatsapp"}


class HomeBannerConfigValidation(BaseModel):
    @field_validator("indicators", check_fields=False)
    @classmethod
    def validate_indicators(cls, value):
        for item in value or []:
            if item.get("icon") not in ALLOWED_ICONS:
                raise ValueError("Icono de indicador no permitido")
        return value

    @field_validator("appearance", check_fields=False)
    @classmethod
    def validate_appearance(cls, value):
        if value is None:
            return value
        if value.get("type", "gradient") not in {"solid", "gradient"}:
            raise ValueError("Tipo de fondo no permitido")
        import re
        for key in ("primary", "secondary"):
            color = value.get(key)
            if color is not None and not re.fullmatch(r"#[0-9a-fA-F]{6}", str(color)):
                raise ValueError("El fondo solo acepta colores hexadecimales")
        return value


class HomeBannerCreateCmd(HomeBannerConfigValidation):
    banner_es: Optional[str] = Field(default=None, max_length=500)
    banner_pr: Optional[str] = Field(default=None, max_length=500)
    banner_en: Optional[str] = Field(default=None, max_length=500)
    enable: bool = Field(default=True)
    content: dict[str, Any] = Field(default_factory=dict)
    indicators: list[dict[str, Any]] = Field(default_factory=list, max_length=3)
    appearance: dict[str, Any] = Field(default_factory=dict)
    show_image: bool = True
    show_indicators: bool = True


class HomeBannerUpdateCmd(HomeBannerConfigValidation):
    id: UUID
    banner_es: Optional[str] = Field(default=None, max_length=500)
    banner_pr: Optional[str] = Field(default=None, max_length=500)
    banner_en: Optional[str] = Field(default=None, max_length=500)
    enable: Optional[bool] = None
    content: Optional[dict[str, Any]] = None
    indicators: Optional[list[dict[str, Any]]] = Field(default=None, max_length=3)
    appearance: Optional[dict[str, Any]] = None
    show_image: Optional[bool] = None
    show_indicators: Optional[bool] = None


class HomeBannerReadDTO(BaseModel):
    id: UUID
    banner_es: Optional[str] = None
    banner_pr: Optional[str] = None
    banner_en: Optional[str] = None
    enable: bool
    created_at: datetime
    created_by: Optional[str] = None
    updated_at: datetime
    content: dict[str, Any] = Field(default_factory=dict)
    indicators: list[dict[str, Any]] = Field(default_factory=list)
    appearance: dict[str, Any] = Field(default_factory=dict)
    show_image: bool = True
    show_indicators: bool = True

    model_config = ConfigDict(from_attributes=True)
