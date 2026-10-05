# app/modules/billing/application/triggers.py
"""Disparador de emisión automática al completar una operación.

Lo llama el módulo de transacciones después de su ``commit``. Con
``BILLING_AUTO_ISSUE=False`` no hace nada: la emisión queda manual desde el
backoffice. Corre en una tarea aparte con su propia sesión para que el cierre
de la operación nunca espere a APISUNAT ni falle por culpa de la facturación.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional
from uuid import UUID

from app.core.settings import get_settings
from app.modules.transactions.domain.enums import TransactionStatus

logger = logging.getLogger(__name__)

_background_tasks: set[asyncio.Task] = set()


def should_auto_issue(previous_status, new_status) -> bool:
    settings = get_settings()
    if not (settings.BILLING_ENABLED and settings.BILLING_AUTO_ISSUE):
        return False
    if new_status != TransactionStatus.completed:
        return False
    return previous_status != TransactionStatus.completed


def maybe_schedule_auto_issue(transaction_id: UUID, previous_status, new_status) -> Optional[asyncio.Task]:
    if not should_auto_issue(previous_status, new_status):
        return None
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None
    task = loop.create_task(auto_issue(transaction_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


async def auto_issue(transaction_id: UUID) -> None:
    # Imports perezosos: evitan el ciclo transactions → billing → transactions.
    from app.db.base import AsyncSessionLocal
    from app.modules.billing.adapters.dependencies import build_apisunat_client
    from app.modules.billing.application.use_cases import BillingDisabledError, IssueInvoiceUseCase
    from app.modules.billing.infrastructure.repository import SQLAlchemyBillingRepository

    settings = get_settings()
    async with AsyncSessionLocal() as session:
        repo = SQLAlchemyBillingRepository(session)
        use_case = IssueInvoiceUseCase(repo, build_apisunat_client(settings), settings)
        try:
            dto = await use_case.execute(transaction_id, actor="auto")
            logger.info(
                "Comprobante %s emitido automáticamente para la operación %s (estado %s)",
                dto.full_number,
                transaction_id,
                dto.status,
            )
        except (ValueError, LookupError, BillingDisabledError) as exc:
            logger.info("Emisión automática omitida para %s: %s", transaction_id, exc)
        except Exception:
            logger.exception("Fallo inesperado al emitir automáticamente la operación %s", transaction_id)
