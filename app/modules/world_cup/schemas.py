from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.world_cup.enums import ExchangeRateScope


class MatchRead(BaseModel):
    id: UUID
    provider_id: str
    stage: Optional[str] = None
    home_team: str
    away_team: str
    home_team_code: Optional[str] = None
    away_team_code: Optional[str] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    starts_at: datetime
    status: str
    selected: bool
    last_synced_at: datetime
    coupon_id: Optional[UUID] = None
    coupon_code: Optional[str] = None
    coupon_status: Optional[str] = None
    coupon_discount_percentage: Optional[float] = None
    coupon_max_uses: Optional[int] = None
    coupon_exchange_rate_scope: Optional[ExchangeRateScope] = None
    model_config = ConfigDict(from_attributes=True)


class CampaignUpdate(BaseModel):
    enabled: bool
    mode: str = Field(pattern="^(REVIEW|AUTOMATIC)$")
    default_discount_percentage: float = Field(gt=0, le=100)
    default_max_uses: int = Field(gt=0)
    exchange_rate_scope: ExchangeRateScope
    code_template: str = Field(min_length=3, max_length=80)
    notification_emails: list[str] = Field(default_factory=list)

class CampaignRead(CampaignUpdate):
    id: UUID
    name: str
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MatchSelection(BaseModel):
    selected: bool
    discount_percentage: Optional[float] = Field(default=None, gt=0, le=100)
    max_uses: Optional[int] = Field(default=None, gt=0)
    exchange_rate_scope: Optional[ExchangeRateScope] = None


class PublicCouponDTO(BaseModel):
    code: str
    discount_percentage: float
    exchange_rate_scope: ExchangeRateScope
    ends_at_estimate: datetime


class PublicMatchDTO(BaseModel):
    home_team: str
    away_team: str
    home_team_code: Optional[str] = None
    away_team_code: Optional[str] = None
    stage: Optional[str] = None
    starts_at: datetime
    status: Optional[str] = None
    coupon: PublicCouponDTO


class PublicLiveResponse(BaseModel):
    live: list[PublicMatchDTO] = Field(default_factory=list)
    next: Optional[PublicMatchDTO] = None


class NotificationRead(BaseModel):
    id: UUID
    kind: str
    title: str
    message: str
    match_id: Optional[UUID] = None
    read_at: Optional[datetime] = None
    email_status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
