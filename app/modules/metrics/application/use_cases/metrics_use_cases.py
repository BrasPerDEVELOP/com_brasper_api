# app/modules/metrics/application/use_cases/metrics_use_cases.py
"""Casos de uso del módulo de métricas."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.coin.domain.enums import Currency
from app.modules.metrics.application.schemas import WeeklyMetricsDTO
from app.modules.metrics.interfaces.metrics_repository import (
    MetricsRepositoryInterface,
)

# Granularidades soportadas y nº de buckets por defecto cuando no se indica rango.
VALID_GRANULARITIES = ("day", "week", "month")
DEFAULT_SPAN_DAYS = {"day": 30, "week": 7 * 12, "month": 365}


def _parse_currency(value: str, field: str) -> Currency:
    try:
        return Currency((value or "").strip().upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Moneda inválida en {field}: {value!r}",
        )


def _parse_date(value: Optional[str], field: str) -> Optional[date]:
    if not value or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Fecha inválida en {field}: {value!r} (formato YYYY-MM-DD)",
        )


def _parse_agent_id(value: Optional[str]) -> Optional[UUID]:
    if not value or not value.strip():
        return None
    try:
        return UUID(value.strip())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"agent_id inválido: {value!r}",
        )


class GetWeeklyMetricsUseCase:
    def __init__(self, repo: MetricsRepositoryInterface):
        self.repo = repo

    async def execute(
        self,
        *,
        origin_currency: str,
        destination_currency: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        granularity: Optional[str] = None,
        status: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> WeeklyMetricsDTO:
        origin = _parse_currency(origin_currency, "origin_currency")
        destination = _parse_currency(destination_currency, "destination_currency")
        gran = (granularity or "week").strip().lower()
        if gran not in VALID_GRANULARITIES:
            # Nota: el módulo `status` de FastAPI queda sombreado por el parámetro
            # homónimo dentro de este método, por eso se usa el código numérico.
            raise HTTPException(
                status_code=422,
                detail=f"granularity inválida: {granularity!r} (day|week|month)",
            )
        df = _parse_date(date_from, "date_from")
        dt = _parse_date(date_to, "date_to")

        today = datetime.now(timezone.utc).date()
        if dt is None:
            dt = today
        if df is None:
            df = dt - timedelta(days=DEFAULT_SPAN_DAYS[gran] - 1)
        if df > dt:
            df, dt = dt, df

        data = await self.repo.period_metrics(
            origin_currency=origin,
            destination_currency=destination,
            date_from=df,
            date_to=dt,
            granularity=gran,
            status=(status or None),
            agent_id=_parse_agent_id(agent_id),
        )
        return WeeklyMetricsDTO(**data)
