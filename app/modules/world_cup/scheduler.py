import asyncio
import logging
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, text

from app.core.settings import get_settings
from app.db.base import AsyncSessionLocal
from app.modules.world_cup.models import AdminNotification, WorldCupCampaign
from app.modules.world_cup.models import WorldCupMatch
from app.modules.transactions.domain.models import Coupon
from app.modules.world_cup.provider import FootballDataProvider
from app.modules.world_cup.service import WorldCupService

logger = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler | None = None


async def _run_locked(live_only: bool) -> None:
    async with AsyncSessionLocal() as db:
        locked = await db.scalar(text("SELECT pg_try_advisory_lock(20260617)"))
        if not locked:
            return
        try:
            settings = get_settings()
            campaign = (await db.execute(select(WorldCupCampaign).where(WorldCupCampaign.deleted.is_(False)))).scalars().first()
            if not campaign or not campaign.enabled or not settings.FOOTBALL_DATA_API_TOKEN:
                return
            service = WorldCupService(db, FootballDataProvider(settings.FOOTBALL_DATA_API_TOKEN, settings.FOOTBALL_DATA_COMPETITION_CODE))
            await service.sync(live_only=live_only)
            if live_only:
                await _suspend_stale_coupons(db)
            await _send_pending_emails(db, campaign)
        except Exception:
            logger.exception("Falló la sincronización programada del Mundial")
            await _suspend_stale_coupons(db)
        finally:
            await db.execute(text("SELECT pg_advisory_unlock(20260617)"))


async def _suspend_stale_coupons(db) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
    rows = (await db.execute(select(Coupon, WorldCupMatch).join(WorldCupMatch, Coupon.match_id == WorldCupMatch.id).where(
        Coupon.coupon_type == "MATCH", Coupon.lifecycle_status == "ACTIVE", WorldCupMatch.last_synced_at < cutoff
    ))).all()
    for coupon, match in rows:
        coupon.lifecycle_status = "SUSPENDED"
        coupon.is_active = False
        key = f"provider-stale:{match.id}:{match.last_synced_at.isoformat()}"
        exists = await db.scalar(select(AdminNotification.id).where(AdminNotification.dedupe_key == key))
        if not exists:
            db.add(AdminNotification(kind="PROVIDER_STALE", title="Cupón suspendido por falta de datos", message=f"Se suspendió {coupon.code} porque football-data.org no confirmó el estado de {match.home_team} vs {match.away_team}.", match_id=match.id, dedupe_key=key))
    await db.commit()


async def _send_pending_emails(db, campaign: WorldCupCampaign) -> None:
    settings = get_settings()
    if not settings.SMTP_HOST or not campaign.notification_emails:
        return
    items = (await db.execute(select(AdminNotification).where(AdminNotification.email_status.in_(["PENDING", "FAILED"]), AdminNotification.email_attempts < 3))).scalars().all()
    for item in items:
        try:
            await asyncio.to_thread(_send_email, settings, campaign.notification_emails, item)
            item.email_status = "SENT"
        except Exception:
            item.email_status = "FAILED"
            logger.exception("No se pudo enviar alerta del Mundial")
        item.email_attempts += 1
    await db.commit()


def _send_email(settings, recipients: list[str], item: AdminNotification) -> None:
    msg = EmailMessage()
    msg["Subject"] = item.title
    msg["From"] = settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME
    msg["To"] = ", ".join(recipients)
    msg.set_content(item.message)
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
        if settings.SMTP_USE_TLS:
            smtp.starttls()
        if settings.SMTP_USERNAME:
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        smtp.send_message(msg)


def start_scheduler() -> AsyncIOScheduler | None:
    global _scheduler
    if not get_settings().WORLD_CUP_SCHEDULER_ENABLED:
        return None
    _scheduler = AsyncIOScheduler(timezone="UTC")
    # Partidos en vivo: cada 5 min. Activa el cupón al detectar LIVE y lo apaga
    # al detectar FINISHED, con un retraso máximo de ~5 min tras el pitazo final.
    _scheduler.add_job(_run_locked, "interval", minutes=5, args=[True], id="world-cup-live", max_instances=1, coalesce=True)
    # Próximos partidos (detección de inicio / reprogramaciones): cada 15 min.
    _scheduler.add_job(_run_locked, "interval", minutes=15, args=[False], id="world-cup-upcoming", max_instances=1, coalesce=True)
    # Calendario completo: cada 6 h.
    _scheduler.add_job(_run_locked, "interval", hours=6, args=[False], id="world-cup-fixtures", max_instances=1, coalesce=True)
    _scheduler.start()
    return _scheduler


def stop_scheduler() -> None:
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
