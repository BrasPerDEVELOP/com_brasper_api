from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.model_base import ORMBaseModel
from app.modules.world_cup.enums import ExchangeRateScope


class WorldCupMatch(ORMBaseModel):
    __tablename__ = "matches"
    __table_args__ = {"schema": "world_cup"}

    provider_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    stage: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    home_team: Mapped[str] = mapped_column(String(120), nullable=False)
    away_team: Mapped[str] = mapped_column(String(120), nullable=False)
    home_team_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    away_team_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    home_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    away_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="SCHEDULED", index=True)
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class WorldCupCampaign(ORMBaseModel):
    __tablename__ = "campaign"
    __table_args__ = {"schema": "world_cup"}

    name: Mapped[str] = mapped_column(String(120), nullable=False, default="Mundial 2026")
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="REVIEW")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default_discount_percentage: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False, default=10)
    default_max_uses: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    default_per_user_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    origin_currency: Mapped[str] = mapped_column(String(10), nullable=False, default="PEN")
    destination_currency: Mapped[str] = mapped_column(String(10), nullable=False, default="BRL")
    code_template: Mapped[str] = mapped_column(String(80), nullable=False, default="MUNDIAL-{HOME}-{AWAY}")
    notification_emails: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    @property
    def exchange_rate_scope(self) -> ExchangeRateScope:
        return ExchangeRateScope.from_currencies(self.origin_currency, self.destination_currency)

    @exchange_rate_scope.setter
    def exchange_rate_scope(self, value: ExchangeRateScope | str) -> None:
        scope = ExchangeRateScope(value)
        origin, destination = scope.currencies
        self.origin_currency = origin.value if origin else "ALL"
        self.destination_currency = destination.value if destination else "ALL"


class CouponRedemption(ORMBaseModel):
    __tablename__ = "coupon_redemptions"
    __table_args__ = {"schema": "world_cup"}

    coupon_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("transaction.coupons.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("user.user.id", ondelete="CASCADE"), nullable=False)
    transaction_id: Mapped[Optional[UUID]] = mapped_column(PgUUID(as_uuid=True), ForeignKey("transaction.transactions.id", ondelete="SET NULL"), nullable=True)


class AdminNotification(ORMBaseModel):
    __tablename__ = "notifications"
    __table_args__ = {"schema": "world_cup"}

    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    message: Mapped[str] = mapped_column(String(1000), nullable=False)
    match_id: Mapped[Optional[UUID]] = mapped_column(PgUUID(as_uuid=True), ForeignKey("world_cup.matches.id", ondelete="CASCADE"), nullable=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    email_status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    email_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dedupe_key: Mapped[str] = mapped_column(String(180), nullable=False, unique=True)
