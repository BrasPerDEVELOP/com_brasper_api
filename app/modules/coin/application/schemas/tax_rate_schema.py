# app/modules/coin/application/schemas/tax_rate_schema.py
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.coin.domain.enums import Currency


class TaxRateCreateCmd(BaseModel):
    coin_a: Currency
    coin_b: Currency
    tax: float = 0


class TaxRateUpdateCmd(BaseModel):
    id: UUID
    coin_a: Optional[Currency] = None
    coin_b: Optional[Currency] = None
    tax: Optional[float] = None


class TaxRateReadDTO(BaseModel):
    id: UUID
    coin_a: Currency
    coin_b: Currency
    tax: float

    model_config = ConfigDict(from_attributes=True)
