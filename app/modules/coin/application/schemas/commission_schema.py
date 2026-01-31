# app/modules/coin/application/schemas/commission_schema.py
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.coin.domain.enums import Currency


class CommissionCreateCmd(BaseModel):
    coin_a: Currency
    coin_b: Currency
    percentage: float = 0
    reverse: bool = False
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None


class CommissionUpdateCmd(BaseModel):
    id: UUID
    coin_a: Optional[Currency] = None
    coin_b: Optional[Currency] = None
    percentage: Optional[float] = None
    reverse: Optional[bool] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None


class CommissionReadDTO(BaseModel):
    id: UUID
    coin_a: Currency
    coin_b: Currency
    percentage: float
    reverse: bool
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)
