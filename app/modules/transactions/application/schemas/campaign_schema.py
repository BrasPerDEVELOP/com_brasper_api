"""Reglas comerciales de campañas de cupones; nunca instrucciones para el LLM."""
from datetime import datetime
from app.modules.coin.domain.enums import Currency
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


class CampaignDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=2, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    discount_percentage: float = Field(ge=0, le=100, allow_inf_nan=False)
    max_uses: int = Field(gt=0)
    per_user_limit: int = Field(default=1, gt=0)
    origin_currency: Currency
    destination_currency: Currency
    start_date: datetime
    end_date: datetime
    campaign_rules: CampaignRules

    @model_validator(mode="after")
    def dates_and_pair(self):
        if self.start_date.tzinfo is None or self.end_date.tzinfo is None or self.end_date <= self.start_date:
            raise ValueError("Inicio y fin deben incluir zona horaria, con fin posterior al inicio")
        if self.origin_currency == self.destination_currency:
            raise ValueError("Origen y destino deben ser distintos")
        return self
