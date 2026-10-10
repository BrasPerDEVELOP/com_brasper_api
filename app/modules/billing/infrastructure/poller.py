# app/modules/billing/infrastructure/poller.py
"""Consulta periódica de comprobantes enviados (APISUNAT no tiene webhooks).

Cada ciclo toma un ``pg_try_advisory_lock`` para que, con varias réplicas de la
API, solo una procese los pendientes; las demás simplemente esperan al
siguiente ciclo. El mismo patrón que usó el scheduler del Mundial.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from sqlalchemy import text

from app.core.settings import get_settings

logger = logging.getLogger(__name__)

# Clave arbitraria y estable del bloqueo consultivo de este trabajo.
BILLING_POLL_LOCK_KEY = 848_201_001


class InvoicePoller:
    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._stopping = False

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stopping = False
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stopping = True
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except (asyncio.CancelledError, Exception):
            pass
        self._task = None

    async def _run(self) -> None:
        interval = max(5, int(get_settings().BILLING_POLL_INTERVAL_SECONDS))
        logger.info("Poller de comprobantes iniciado (cada %ss)", interval)
        while not self._stopping:
            try:
                changed = await self.tick()
                if changed:
                    logger.info("Poller de comprobantes: %s comprobante(s) cambiaron de estado", changed)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Poller de comprobantes falló en este ciclo: %s", exc)
            await asyncio.sleep(interval)

    async def tick(self) -> int:
        """Un ciclo: devuelve cuántos comprobantes cambiaron de estado.

        El bloqueo consultivo es de SESIÓN de Postgres: hay que liberarlo en la misma
        conexión que lo tomó. Por eso vive en una conexión dedicada, separada de la
        sesión ORM de trabajo, que hace ``commit`` por comprobante y con cada commit
        devuelve su conexión al pool (si el lock viviera ahí, el unlock correría en
        otra conexión y el lock quedaría pegado a una conexión del pool).
        """
        from app.db.base import AsyncSessionLocal, engine
        from app.modules.billing.adapters.dependencies import build_apisunat_client
        from app.modules.billing.application.use_cases import (
            PollInvoiceUseCase,
            PollPendingInvoicesUseCase,
            RecoverStaleReservedUseCase,
        )
        from app.modules.billing.infrastructure.repository import SQLAlchemyBillingRepository
        from app.shared.services.file_service import file_service

        settings = get_settings()
        if not settings.BILLING_ENABLED:
            return 0
        async with engine.connect() as lock_conn:
            locked = (
                await lock_conn.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": BILLING_POLL_LOCK_KEY})
            ).scalar()
            await lock_conn.commit()
            if not locked:
                return 0
            try:
                client = build_apisunat_client(settings)
                async with AsyncSessionLocal() as session:
                    repo = SQLAlchemyBillingRepository(session)
                    recovered = await RecoverStaleReservedUseCase(repo, client, settings).execute()
                    poll = PollInvoiceUseCase(repo, client, settings, file_service)
                    return recovered + await PollPendingInvoicesUseCase(poll, repo).execute()
            finally:
                await lock_conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": BILLING_POLL_LOCK_KEY})
                await lock_conn.commit()


invoice_poller = InvoicePoller()
