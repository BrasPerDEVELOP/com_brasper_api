from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.db.base import get_db
from app.modules.auth.infrastructure.dependencies import require_permission
from app.modules.transactions.domain.models import Coupon
from app.modules.world_cup.enums import ExchangeRateScope
from app.modules.world_cup.models import AdminNotification, WorldCupCampaign, WorldCupMatch
from app.modules.world_cup.provider import FootballDataProvider
from app.modules.world_cup.schemas import (
    CampaignRead,
    CampaignUpdate,
    MatchRead,
    MatchSelection,
    NotificationRead,
    PublicCouponDTO,
    PublicLiveResponse,
    PublicMatchDTO,
)
from app.modules.world_cup.service import WorldCupService, estimate_match_end, list_matches_with_coupons

router = APIRouter(prefix="/world-cup", tags=["world-cup"], dependencies=[Depends(require_permission("world_cup.view"))])

# Router PÚBLICO (sin require_permission). Su ruta /world-cup/public/ está en la allowlist
# del TokenAuthMiddleware, igual que /home-banner/home-bootstrap.
public_router = APIRouter(prefix="/world-cup/public", tags=["world-cup-public"])


def _public_match_dto(match: WorldCupMatch, coupon: Coupon, *, include_status: bool) -> PublicMatchDTO:
    return PublicMatchDTO(
        home_team=match.home_team,
        away_team=match.away_team,
        home_team_code=match.home_team_code,
        away_team_code=match.away_team_code,
        stage=match.stage,
        starts_at=match.starts_at,
        status=match.status if include_status else None,
        coupon=PublicCouponDTO(
            code=coupon.code,
            discount_percentage=float(coupon.discount_percentage),
            exchange_rate_scopes=ExchangeRateScope.normalize_many(
                coupon.exchange_rate_scopes,
                fallback=ExchangeRateScope.from_currencies(coupon.origin_currency, coupon.destination_currency),
            ),
            ends_at_estimate=estimate_match_end(match.starts_at),
        ),
    )


@public_router.get("/live", response_model=PublicLiveResponse)
async def public_live(db: AsyncSession = Depends(get_db)):
    campaign = (await db.execute(select(WorldCupCampaign).where(WorldCupCampaign.deleted.is_(False)))).scalars().first()
    if not campaign or not campaign.enabled:
        return PublicLiveResponse(live=[], next=None)

    live_rows = (await db.execute(
        select(WorldCupMatch, Coupon).join(Coupon, Coupon.match_id == WorldCupMatch.id).where(
            WorldCupMatch.deleted.is_(False),
            Coupon.deleted.is_(False),
            WorldCupMatch.status == "LIVE",
            Coupon.lifecycle_status == "ACTIVE",
        ).order_by(WorldCupMatch.starts_at)
    )).all()
    live = [_public_match_dto(match, coupon, include_status=True) for match, coupon in live_rows]

    next_row = (await db.execute(
        select(WorldCupMatch, Coupon).join(Coupon, Coupon.match_id == WorldCupMatch.id).where(
            WorldCupMatch.deleted.is_(False),
            Coupon.deleted.is_(False),
            WorldCupMatch.status == "SCHEDULED",
            Coupon.lifecycle_status.in_(["APPROVED_WAITING", "ACTIVE"]),
        ).order_by(WorldCupMatch.starts_at).limit(1)
    )).first()
    next_dto = _public_match_dto(next_row[0], next_row[1], include_status=False) if next_row else None

    return PublicLiveResponse(live=live, next=next_dto)


def service(db: AsyncSession = Depends(get_db)) -> WorldCupService:
    settings = get_settings()
    return WorldCupService(db, FootballDataProvider(settings.FOOTBALL_DATA_API_TOKEN, settings.FOOTBALL_DATA_COMPETITION_CODE))


@router.get("/campaign", response_model=CampaignRead)
async def get_campaign(svc: WorldCupService = Depends(service)):
    campaign = await svc.get_or_create_campaign()
    await svc.session.commit()
    await svc.session.refresh(campaign)
    return campaign


@router.put("/campaign", response_model=CampaignRead, dependencies=[Depends(require_permission("world_cup.manage"))])
async def update_campaign(body: CampaignUpdate, svc: WorldCupService = Depends(service)):
    campaign = await svc.get_or_create_campaign()
    payload = body.model_dump(exclude={"exchange_rate_scope", "exchange_rate_scopes"})
    for field, value in payload.items():
        setattr(campaign, field, value)
    campaign.set_exchange_rate_scopes(body.exchange_rate_scopes)
    await svc.session.commit()
    await svc.session.refresh(campaign)
    return campaign


@router.get("/matches", response_model=list[MatchRead])
async def matches(db: AsyncSession = Depends(get_db)):
    return await list_matches_with_coupons(db)


@router.post("/matches/{match_id}/selection", response_model=MatchRead, dependencies=[Depends(require_permission("world_cup.manage"))])
async def select_match(match_id: UUID, body: MatchSelection, svc: WorldCupService = Depends(service)):
    try:
        await svc.select_match(
            match_id,
            body.selected,
            discount_percentage=body.discount_percentage,
            max_uses=body.max_uses,
            exchange_rate_scopes=body.provided_exchange_rate_scopes,
        )
        return next(item for item in await list_matches_with_coupons(svc.session) if item["id"] == match_id)
    except (ValueError, StopIteration) as exc:
        raise HTTPException(400, str(exc))


@router.post("/coupons/{coupon_id}/{action}", dependencies=[Depends(require_permission("world_cup.approve"))])
async def coupon_action(coupon_id: UUID, action: str, svc: WorldCupService = Depends(service)):
    try:
        coupon = await svc.set_coupon_status(coupon_id, action)
        return {"id": coupon.id, "status": coupon.lifecycle_status}
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/sync", dependencies=[Depends(require_permission("world_cup.manage"))])
async def sync(svc: WorldCupService = Depends(service)):
    try:
        return {"synced": await svc.sync()}
    except Exception as exc:
        raise HTTPException(502, f"No se pudo sincronizar football-data.org: {exc}")


@router.get("/notifications", response_model=list[NotificationRead])
async def notifications(db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(AdminNotification).where(AdminNotification.deleted.is_(False)).order_by(AdminNotification.created_at.desc()).limit(100))).scalars().all()


@router.post("/notifications/{notification_id}/read", response_model=NotificationRead)
async def read_notification(notification_id: UUID, db: AsyncSession = Depends(get_db)):
    item = await db.get(AdminNotification, notification_id)
    if not item:
        raise HTTPException(404, "Notificación no encontrada")
    item.read_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(item)
    return item
