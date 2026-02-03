# app/modules/coin/application/schemas/commission_schema.py
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.coin.domain.enums import Currency


class CommissionCreateCmd(BaseModel):
    coin_a: Currency
    coin_b: Currency
    percentage: float = 0
    reverse: Decimal = Field(default=Decimal("0"), description="Reversa en valor decimal, ej. 0.5")
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None


class CommissionUpdateCmd(BaseModel):
    id: UUID
    coin_a: Optional[Currency] = None
    coin_b: Optional[Currency] = None
    percentage: Optional[float] = None
    reverse: Optional[Decimal] = Field(default=None, description="Reversa en valor decimal")
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None


class CommissionReadDTO(BaseModel):
    id: UUID
    coin_a: Currency
    coin_b: Currency
    percentage: float
    reverse: Decimal
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    created_at: datetime
    created_by: Optional[str] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
