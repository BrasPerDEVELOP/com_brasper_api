from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

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
    coupon_exchange_rate_scopes: list[ExchangeRateScope] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class CampaignUpdate(BaseModel):
    enabled: bool
    mode: str = Field(pattern="^(REVIEW|AUTOMATIC)$")
    default_discount_percentage: float = Field(gt=0, le=100)
    default_max_uses: int = Field(gt=0)
    exchange_rate_scopes: Optional[list[ExchangeRateScope]] = None
    exchange_rate_scope: Optional[ExchangeRateScope] = None
    code_template: str = Field(min_length=3, max_length=80)
    notification_emails: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_exchange_rate_scopes(self):
        self.exchange_rate_scopes = ExchangeRateScope.normalize_many(
            self.exchange_rate_scopes,
            fallback=self.exchange_rate_scope,
        )
        self.exchange_rate_scope = self.exchange_rate_scopes[0]
        return self

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
    exchange_rate_scopes: Optional[list[ExchangeRateScope]] = None

    @property
    def effective_exchange_rate_scopes(self) -> list[ExchangeRateScope]:
        return ExchangeRateScope.normalize_many(
            self.exchange_rate_scopes,
            fallback=self.exchange_rate_scope,
        )

    @property
    def provided_exchange_rate_scopes(self) -> list[ExchangeRateScope] | None:
        if self.exchange_rate_scopes is None and self.exchange_rate_scope is None:
            return None
        return self.effective_exchange_rate_scopes


class PublicCouponDTO(BaseModel):
    code: str
    discount_percentage: float
    exchange_rate_scopes: list[ExchangeRateScope] = Field(default_factory=list)
    ends_at_estimate: datetime

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_exchange_rate_scope(cls, data):
        if isinstance(data, dict) and not data.get("exchange_rate_scopes") and data.get("exchange_rate_scope"):
            return {**data, "exchange_rate_scopes": [data["exchange_rate_scope"]]}
        return data

    @model_validator(mode="after")
    def normalize_exchange_rate_scopes(self):
        self.exchange_rate_scopes = ExchangeRateScope.normalize_many(self.exchange_rate_scopes)
        return self

    @computed_field
    @property
    def exchange_rate_scope(self) -> ExchangeRateScope:
        return self.exchange_rate_scopes[0] if self.exchange_rate_scopes else ExchangeRateScope.all


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
