"""Validación de ``Coupon.campaign_rules`` (columna de la migración 083).

La administración de campañas se retiró de la API principal (vive en com_brasper_ia).
Se conserva solo este esquema porque el registro de operaciones (``campaign_policy.discount_for``)
y los DTO de cupones siguen validando reglas de filas que ya existan; no se pueden crear
reglas nuevas desde la API (``CreateCouponUseCase``/``UpdateCouponUseCase`` las rechazan).
"""
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CampaignCopy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=2000)
    media_id: str | None = Field(default=None, max_length=60)


class CampaignRules(BaseModel):
    model_config = ConfigDict(extra="forbid")
    segment: Literal["all", "first_transfer", "returning"]
    timezone: str = "America/Lima"
    minimum_amount: float = Field(default=0, ge=0, allow_inf_nan=False)
    maximum_amount: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    maximum_discount: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    priority: int = Field(default=0, ge=0, le=100)
    # Deliberately explicit: the financial engine selects exactly one campaign.
    combination: Literal["exclusive"] = "exclusive"
    messages: dict[Literal["es", "pt"], CampaignCopy]

    @model_validator(mode="after")
    def validate_rules(self):
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Zona horaria no válida") from exc
        if self.maximum_amount is not None and self.maximum_amount < self.minimum_amount:
            raise ValueError("El máximo debe ser mayor o igual al mínimo")
        if set(self.messages) != {"es", "pt"}:
            raise ValueError("La campaña requiere condiciones aprobadas en español y portugués")
        return self

