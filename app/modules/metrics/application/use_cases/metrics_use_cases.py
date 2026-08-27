# app/modules/metrics/application/use_cases/metrics_use_cases.py
"""Casos de uso del módulo de métricas."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.coin.domain.enums import Currency
from app.modules.metrics.application.schemas import MetricsOverviewDTO, WeeklyMetricsDTO
from app.modules.metrics.interfaces.metrics_repository import (
    MetricsRepositoryInterface,
)

# Granularidades soportadas y nº de buckets por defecto cuando no se indica rango.
VALID_GRANULARITIES = ("day", "week", "month")
DEFAULT_SPAN_DAYS = {"day": 30, "week": 7 * 12, "month": 365}
VALID_CORRIDORS = ("all", "PEN_BRL", "BRL_PEN", "USD_BRL", "BRL_USD")


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


def _parse_tag_ids(values: Optional[list[str]]) -> list[UUID]:
    parsed: list[UUID] = []
    for value in values or []:
        try:
            tag_id = UUID(value.strip())
        except (AttributeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"tag_id inválido: {value!r}",
            )
        if tag_id not in parsed:
            parsed.append(tag_id)
    return parsed


def _resolve_range(
    *,
    date_from: Optional[str],
    date_to: Optional[str],
    granularity: Optional[str],
) -> tuple[date, date, str]:
    gran = (granularity or "week").strip().lower()
    if gran not in VALID_GRANULARITIES:
        raise HTTPException(
            status_code=422,
            detail=f"granularity inválida: {granularity!r} (day|week|month)",
        )
    df = _parse_date(date_from, "date_from")
    dt = _parse_date(date_to, "date_to")
    today = datetime.now(timezone.utc).date()
    dt = dt or today
    df = df or dt - timedelta(days=DEFAULT_SPAN_DAYS[gran] - 1)
    if df > dt:
        df, dt = dt, df
    return df, dt, gran


class GetMetricsOverviewUseCase:
    def __init__(self, repo: MetricsRepositoryInterface):
        self.repo = repo

    async def execute(
        self,
        *,
        corridor: str = "all",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        granularity: Optional[str] = None,
        status: Optional[str] = None,
        agent_id: Optional[str] = None,
        tag_ids: Optional[list[str]] = None,
    ) -> MetricsOverviewDTO:
        normalized_corridor = (corridor or "all").strip()
        if normalized_corridor.lower() == "all":
            normalized_corridor = "all"
        else:
            normalized_corridor = normalized_corridor.upper()
        if normalized_corridor not in VALID_CORRIDORS:
            raise HTTPException(
                status_code=422,
                detail=f"corridor inválido: {corridor!r}",
            )

        df, dt, gran = _resolve_range(
            date_from=date_from,
            date_to=date_to,
            granularity=granularity,
        )
        data = await self.repo.overview_metrics(
            corridor=normalized_corridor,
            date_from=df,
            date_to=dt,
            granularity=gran,
            status=status or None,
            agent_id=_parse_agent_id(agent_id),
            tag_ids=_parse_tag_ids(tag_ids),
        )
        return MetricsOverviewDTO(**data)


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
        df, dt, gran = _resolve_range(
            date_from=date_from,
            date_to=date_to,
            granularity=granularity,
        )

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
