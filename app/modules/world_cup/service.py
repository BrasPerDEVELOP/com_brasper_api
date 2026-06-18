from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.transactions.domain.models import Coupon
from app.modules.coin.domain.enums import Currency
from app.modules.world_cup.models import AdminNotification, WorldCupCampaign, WorldCupMatch
from app.modules.world_cup.enums import ExchangeRateScope
from app.modules.world_cup.provider import ProviderMatch, SportsProvider

# Duración máxima razonable de un partido. Tras starts_at + esta ventana, el cupón
# del partido NUNCA debe seguir ACTIVE aunque el proveedor no confirme FINISHED.
MATCH_MAX_DURATION = timedelta(hours=4)


def estimate_match_end(starts_at: datetime) -> datetime:
    """Estimación dura del fin del partido: starts_at + MATCH_MAX_DURATION."""
    return starts_at + MATCH_MAX_DURATION


class WorldCupService:
    def __init__(self, session: AsyncSession, provider: SportsProvider):
        self.session = session
        self.provider = provider

    async def get_or_create_campaign(self) -> WorldCupCampaign:
        campaign = (await self.session.execute(select(WorldCupCampaign).where(WorldCupCampaign.deleted.is_(False)))).scalars().first()
        if campaign:
            return campaign
        campaign = WorldCupCampaign()
        self.session.add(campaign)
        await self.session.flush()
        return campaign

    async def sync(self, live_only: bool = False) -> int:
        campaign = await self.get_or_create_campaign()
        if live_only:
            incoming = await self.provider.live()
        else:
            now = datetime.now(timezone.utc)
            incoming = await self.provider.fixtures(now - timedelta(days=2), now + timedelta(days=45))
        for fixture in incoming:
            await self._upsert_match(fixture, campaign)
        await self._activate_due_coupons(campaign)
        await self._expire_overdue_coupons()
        await self._create_due_notifications(campaign)
        await self.session.commit()
        return len(incoming)

    async def _upsert_match(self, fixture: ProviderMatch, campaign: WorldCupCampaign) -> None:
        match = (await self.session.execute(select(WorldCupMatch).where(WorldCupMatch.provider_id == fixture.provider_id))).scalar_one_or_none()
        previous_status = match.status if match else None
        if not match:
            match = WorldCupMatch(provider_id=fixture.provider_id, home_team=fixture.home_team, away_team=fixture.away_team, starts_at=fixture.starts_at, status=fixture.status, last_synced_at=datetime.now(timezone.utc))
            self.session.add(match)
        for field in ("stage", "home_team", "away_team", "home_team_code", "away_team_code", "home_score", "away_score", "starts_at", "status", "raw_data"):
            setattr(match, field, getattr(fixture, field))
        match.last_synced_at = datetime.now(timezone.utc)
        await self.session.flush()
        coupon = (await self.session.execute(select(Coupon).where(Coupon.match_id == match.id, Coupon.deleted.is_(False)))).scalar_one_or_none()
        if not coupon:
            return
        if fixture.status == "LIVE" and coupon.lifecycle_status in {"APPROVED_WAITING", "SUSPENDED"} and campaign.enabled:
            coupon.lifecycle_status = "ACTIVE"
            coupon.is_active = True
            coupon.start_date = match.starts_at
        elif fixture.status in {"FINISHED", "CANCELLED"} and coupon.lifecycle_status in {"APPROVED_WAITING", "ACTIVE"}:
            coupon.lifecycle_status = "EXPIRED" if fixture.status == "FINISHED" else "CANCELLED"
            coupon.is_active = False
            coupon.end_date = datetime.now(timezone.utc)
        elif previous_status == "LIVE" and fixture.status == "SCHEDULED" and coupon.lifecycle_status == "ACTIVE":
            coupon.lifecycle_status = "APPROVED_WAITING"
            coupon.is_active = False

    async def _activate_due_coupons(self, campaign: WorldCupCampaign) -> None:
        if not campaign.enabled:
            return
        now = datetime.now(timezone.utc)
        rows = (await self.session.execute(
            select(Coupon, WorldCupMatch).join(WorldCupMatch, Coupon.match_id == WorldCupMatch.id).where(
                Coupon.coupon_type == "MATCH",
                Coupon.lifecycle_status.in_(["APPROVED_WAITING", "SUSPENDED"]),
                WorldCupMatch.starts_at <= now,
                WorldCupMatch.starts_at > now - timedelta(hours=4),
                WorldCupMatch.status.notin_(["FINISHED", "CANCELLED", "POSTPONED"]),
            )
        )).all()
        for coupon, match in rows:
            coupon.lifecycle_status = "ACTIVE"
            coupon.is_active = True
            coupon.start_date = match.starts_at

    async def _expire_overdue_coupons(self) -> None:
        """Salvaguarda dura por tiempo: si un partido superó starts_at + MATCH_MAX_DURATION
        sin que el proveedor confirme FINISHED/CANCELLED, su cupón pasa a EXPIRED y nunca
        queda ACTIVE indefinidamente. Independiente del estado del proveedor."""
        now = datetime.now(timezone.utc)
        rows = (await self.session.execute(
            select(Coupon, WorldCupMatch).join(WorldCupMatch, Coupon.match_id == WorldCupMatch.id).where(
                Coupon.coupon_type == "MATCH",
                Coupon.lifecycle_status.in_(["ACTIVE", "APPROVED_WAITING", "SUSPENDED"]),
                WorldCupMatch.starts_at < now - MATCH_MAX_DURATION,
            )
        )).all()
        for coupon, _match in rows:
            coupon.lifecycle_status = "EXPIRED"
            coupon.is_active = False
            coupon.end_date = now

    async def select_match(
        self,
        match_id: UUID,
        selected: bool,
        *,
        discount_percentage: float | None = None,
        max_uses: int | None = None,
        exchange_rate_scope: ExchangeRateScope | None = None,
    ) -> WorldCupMatch:
        match = await self.session.get(WorldCupMatch, match_id)
        if not match or match.deleted:
            raise ValueError("Partido no encontrado")
        campaign = await self.get_or_create_campaign()
        # Scope efectivo del partido: el recibido por partido, o el de la campaña como default.
        effective_scope = exchange_rate_scope or campaign.exchange_rate_scope
        match.selected = selected
        coupon = (await self.session.execute(select(Coupon).where(Coupon.match_id == match.id, Coupon.deleted.is_(False)))).scalar_one_or_none()
        if selected and not coupon:
            code = await self._unique_code(self._render_code(campaign.code_template, match))
            origin_currency, destination_currency = effective_scope.currencies
            coupon = Coupon(
                code=code,
                discount_percentage=discount_percentage or campaign.default_discount_percentage,
                max_uses=max_uses or campaign.default_max_uses,
                per_user_limit=None,
                origin_currency=origin_currency,
                destination_currency=destination_currency,
                coupon_type="MATCH",
                lifecycle_status="DRAFT" if campaign.mode == "REVIEW" else "APPROVED_WAITING",
                match_id=match.id,
                is_active=False,
            )
            self.session.add(coupon)
        elif selected and coupon and coupon.lifecycle_status in {"DRAFT", "APPROVED_WAITING", "CANCELLED"}:
            origin_currency, destination_currency = effective_scope.currencies
            coupon.discount_percentage = discount_percentage or coupon.discount_percentage
            coupon.max_uses = max_uses or coupon.max_uses
            coupon.per_user_limit = None
            coupon.origin_currency = origin_currency
            coupon.destination_currency = destination_currency
            if coupon.lifecycle_status == "CANCELLED":
                coupon.lifecycle_status = "DRAFT" if campaign.mode == "REVIEW" else "APPROVED_WAITING"
        elif not selected and coupon and coupon.lifecycle_status != "ACTIVE":
            coupon.lifecycle_status = "CANCELLED"
            coupon.is_active = False
        await self.session.commit()
        await self.session.refresh(match)
        return match

    async def set_coupon_status(self, coupon_id: UUID, action: str) -> Coupon:
        coupon = await self.session.get(Coupon, coupon_id)
        if not coupon or coupon.deleted or coupon.coupon_type != "MATCH":
            raise ValueError("Cupón del Mundial no encontrado")
        if action == "approve" and coupon.lifecycle_status == "DRAFT":
            coupon.lifecycle_status = "APPROVED_WAITING"
        elif action == "cancel" and coupon.lifecycle_status != "ACTIVE":
            coupon.lifecycle_status = "CANCELLED"
            coupon.is_active = False
        else:
            raise ValueError("Transición de cupón no permitida")
        await self.session.commit()
        await self.session.refresh(coupon)
        return coupon

    async def _create_due_notifications(self, campaign: WorldCupCampaign) -> None:
        now = datetime.now(timezone.utc)
        rows = (await self.session.execute(
            select(WorldCupMatch, Coupon).join(Coupon, Coupon.match_id == WorldCupMatch.id).where(
                WorldCupMatch.selected.is_(True), Coupon.lifecycle_status == "DRAFT", WorldCupMatch.starts_at > now,
                WorldCupMatch.starts_at <= now + timedelta(hours=24)
            )
        )).all()
        for match, coupon in rows:
            hours = 2 if match.starts_at <= now + timedelta(hours=2) else 24
            key = f"approval:{match.id}:{hours}h"
            exists = await self.session.scalar(select(func.count(AdminNotification.id)).where(AdminNotification.dedupe_key == key))
            if exists:
                continue
            self.session.add(AdminNotification(
                kind="COUPON_APPROVAL", title=f"Cupón pendiente: {match.home_team} vs {match.away_team}",
                message=f"El partido inicia en menos de {hours} horas y el cupón {coupon.code} sigue en borrador.",
                match_id=match.id, dedupe_key=key,
            ))

    async def _unique_code(self, base: str) -> str:
        candidate = base[:72]
        suffix = 1
        while await self.session.scalar(select(func.count(Coupon.id)).where(Coupon.code == candidate)):
            suffix += 1
            candidate = f"{base[:68]}-{suffix}"
        return candidate

    @staticmethod
    def _render_code(template: str, match: WorldCupMatch) -> str:
        home = match.home_team_code or match.home_team[:3]
        away = match.away_team_code or match.away_team[:3]
        value = template.replace("{HOME}", home).replace("{AWAY}", away).replace("{DATE}", match.starts_at.strftime("%m%d"))
        return re.sub(r"[^A-Z0-9-]+", "-", value.upper()).strip("-")


async def list_matches_with_coupons(session: AsyncSession) -> list[dict]:
    rows = (await session.execute(
        select(WorldCupMatch, Coupon).outerjoin(Coupon, (Coupon.match_id == WorldCupMatch.id) & Coupon.deleted.is_(False)).where(WorldCupMatch.deleted.is_(False)).order_by(WorldCupMatch.starts_at)
    )).all()
    return [{
        "id": match.id, "provider_id": match.provider_id, "stage": match.stage,
        "home_team": match.home_team, "away_team": match.away_team,
        "home_team_code": match.home_team_code, "away_team_code": match.away_team_code,
        "home_score": match.home_score, "away_score": match.away_score,
        "starts_at": match.starts_at, "status": match.status, "selected": match.selected,
        "last_synced_at": match.last_synced_at, "coupon_id": coupon.id if coupon else None,
        "coupon_code": coupon.code if coupon else None, "coupon_status": coupon.lifecycle_status if coupon else None,
        "coupon_discount_percentage": coupon.discount_percentage if coupon else None,
        "coupon_max_uses": coupon.max_uses if coupon else None,
        "coupon_exchange_rate_scope": ExchangeRateScope.from_currencies(coupon.origin_currency, coupon.destination_currency) if coupon else None,
    } for match, coupon in rows]
