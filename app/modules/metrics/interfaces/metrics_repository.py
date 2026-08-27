# app/modules/metrics/interfaces/metrics_repository.py
"""Puerto del repositorio de métricas (consumido por el use case)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional
from uuid import UUID

from app.modules.coin.domain.enums import Currency


class MetricsRepositoryInterface(ABC):
    @abstractmethod
    async def overview_metrics(
        self,
        *,
        corridor: str,
        date_from: date,
        date_to: date,
        granularity: str = "week",
        status: Optional[str] = None,
        agent_id: Optional[UUID] = None,
        tag_ids: Optional[list[UUID]] = None,
    ) -> dict:
        """Devuelve todos los agregados coordinados del panel unificado."""
        raise NotImplementedError

    @abstractmethod
    async def period_metrics(
        self,
        *,
        origin_currency: Currency,
        destination_currency: Currency,
        date_from: date,
        date_to: date,
        granularity: str = "week",
        status: Optional[str] = None,
        agent_id: Optional[UUID] = None,
    ) -> dict:
        """Devuelve el dict con ``weeks`` (buckets del periodo) y ``totals``.

        ``granularity`` es uno de ``day`` | ``week`` | ``month``.
        """
        raise NotImplementedError
