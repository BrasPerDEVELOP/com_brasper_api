# app/modules/coin/application/schemas/tax_rate_trial_schema.py
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.coin.domain.enums import Currency


class TaxRateTrialCreateCmd(BaseModel):
    coin_a: Currency
    coin_b: Currency
    tax: Decimal = Field(default=Decimal("0"), description="Tasa decimal, ej. 0.622")


class TaxRateTrialUpdateCmd(BaseModel):
    id: UUID
    coin_a: Optional[Currency] = None
    coin_b: Optional[Currency] = None
    tax: Optional[Decimal] = Field(default=None, description="Tasa decimal, ej. 0.622")


class TaxRateTrialReadDTO(BaseModel):
    id: UUID
    coin_a: Currency
    coin_b: Currency
    tax: Decimal
    created_at: datetime
    created_by: Optional[str] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
