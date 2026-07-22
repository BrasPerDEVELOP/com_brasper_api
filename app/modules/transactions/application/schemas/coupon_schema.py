# app/modules/transactions/application/schemas/coupon_schema.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.coin.domain.enums import Currency


class CouponCreateCmd(BaseModel):
    code: str
    discount_percentage: float
    max_uses: int
    origin_currency: Currency
    destination_currency: Currency
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_active: bool = True
    coupon_type: str = "STANDARD"
    lifecycle_status: str = "ACTIVE"
    per_user_limit: Optional[int] = None
    exchange_rate_scopes: Optional[list[str]] = None


class CouponUpdateCmd(BaseModel):
    id: UUID
    code: Optional[str] = None
    discount_percentage: Optional[float] = None
    max_uses: Optional[int] = None
    origin_currency: Optional[Currency] = None
    destination_currency: Optional[Currency] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_active: Optional[bool] = None
    lifecycle_status: Optional[str] = None
    per_user_limit: Optional[int] = None
    exchange_rate_scopes: Optional[list[str]] = None


class CouponReadDTO(BaseModel):
    id: UUID
    code: str
    discount_percentage: float
    max_uses: int
    origin_currency: Optional[Currency]
    destination_currency: Optional[Currency]
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_active: bool
    created_at: datetime
    created_by: Optional[str] = None
    updated_at: datetime
    coupon_type: str = "STANDARD"
    lifecycle_status: str = "ACTIVE"
    used_count: int = 0
    per_user_limit: Optional[int] = None
    exchange_rate_scopes: Optional[list[str]] = None

    model_config = ConfigDict(from_attributes=True)
