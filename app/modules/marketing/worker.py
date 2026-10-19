"""Persistent outbox. A PostgreSQL advisory lock serializes SMTP across API workers.

An interrupted 'processing' delivery is never retried automatically: SMTP may
already have accepted it. Operators can inspect it without risking duplicates.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import exists, select, text, func

from app.core.settings import get_settings
from app.db.base import AsyncSessionLocal, engine
from app.modules.marketing.mail import send_email
from app.modules.marketing.models import Campaign, Recipient, Suppression

logger = logging.getLogger(__name__)


async def deliver_one(db):
    row = (await db.execute(select(Recipient, Campaign).join(Campaign).where(
        Campaign.status == "queued", Recipient.status == "pending"
    ).order_by(Campaign.created_at, Recipient.email).limit(1))).first()
    if not row:
        # A campaign completes only once every pending recipient is handled.
        items = (await db.execute(select(Campaign).where(Campaign.status == "queued"))).scalars().all()
        for item in items:
            active = (await db.execute(select(exists().where(
                Recipient.campaign_id == item.id, Recipient.status.in_(["pending", "processing"])
            )))).scalar_one()
            if not active:
                item.status = "completed"
        await db.commit()
        return False
    recipient, campaign = row
    if await db.get(Suppression, recipient.email):
        recipient.status = "suppressed"
        await db.commit()
        return True
    attempts = (await db.execute(select(func.count()).select_from(Recipient).where(
        Recipient.attempted_at >= datetime.now(timezone.utc) - timedelta(hours=24)
    ))).scalar_one()
    if attempts >= get_settings().MARKETING_DAILY_LIMIT:
        return False
    recipient.status = "processing"
    recipient.attempted_at = datetime.now(timezone.utc)
    await db.commit()
    try:
        await asyncio.to_thread(send_email, recipient.email, campaign.subject, campaign.body,
                                False, getattr(campaign, "template_key", None))
        recipient.status = "sent"
        recipient.sent_at = datetime.now(timezone.utc)
    except Exception:
        # SMTP exceptions can include addresses and credentials. Never persist their text.
        recipient.status = "failed"
        recipient.error = "SMTP no confirmó el envío. No se reintentó automáticamente."
    await db.commit()
    return True


async def run_worker(stop: asyncio.Event):
    while not stop.is_set():
        try:
            # Session-level advisory lock survives commits during SMTP delivery.
            async with AsyncSessionLocal() as db:
                # Use transaction-level lock on a dedicated connection, so the
                # delivery session can commit without releasing the global lock.
                async with engine.connect() as lock_connection:
                    acquired = (await lock_connection.execute(text("SELECT pg_try_advisory_xact_lock(82461019)"))).scalar()
                    if acquired:
                        await deliver_one(db)
                        try:
                            await asyncio.wait_for(stop.wait(), timeout=get_settings().MARKETING_INTERVAL_SECONDS)
                        except asyncio.TimeoutError:
                            pass
        except Exception:
            logger.error("Marketing: no se pudo procesar la cola; verifica migración y conexión")
        try:
            await asyncio.wait_for(stop.wait(), timeout=2)
        except asyncio.TimeoutError:
            pass
