# app/modules/transactions/application/schemas/coupon_schema.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.coin.domain.enums import Currency
from .campaign_schema import CampaignRules


class CouponCreateCmd(BaseModel):
    code: str
    discount_percentage: float = Field(ge=0, le=100, allow_inf_nan=False)
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
    campaign_rules: Optional[CampaignRules] = None


class CouponUpdateCmd(BaseModel):
    id: UUID
    code: Optional[str] = None
    discount_percentage: Optional[float] = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    max_uses: Optional[int] = None
    origin_currency: Optional[Currency] = None
    destination_currency: Optional[Currency] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_active: Optional[bool] = None
    lifecycle_status: Optional[str] = None
    per_user_limit: Optional[int] = None
    exchange_rate_scopes: Optional[list[str]] = None
    campaign_rules: Optional[CampaignRules] = None
    expected_version: Optional[int] = Field(default=None, ge=1)


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
    campaign_rules: Optional[CampaignRules] = None
    campaign_version: int = 1

    model_config = ConfigDict(from_attributes=True)
