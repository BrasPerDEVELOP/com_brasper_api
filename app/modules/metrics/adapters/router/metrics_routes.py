# app/modules/metrics/adapters/router/metrics_routes.py
"""Rutas del módulo de métricas."""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.modules.auth.infrastructure.dependencies import require_permission
from app.modules.metrics.adapters.dependencies import (
    GetMetricsOverviewUseCaseDep,
    GetWeeklyMetricsUseCaseDep,
)
from app.modules.metrics.application.schemas import MetricsOverviewDTO, WeeklyMetricsDTO

from app.core.routing import LegacyAliasRouter

router = LegacyAliasRouter(tags=["metrics"])


@router.get(
    "/overview",
    response_model=MetricsOverviewDTO,
    dependencies=[Depends(require_permission("metrics.view"))],
)
async def metrics_overview(
    use_case: GetMetricsOverviewUseCaseDep,
    corridor: str = Query("all", description="all | PEN_BRL | BRL_PEN | USD_BRL | BRL_USD"),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD (opcional)"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD (opcional)"),
    granularity: Optional[str] = Query("week", description="day | week | month | year"),
    status: Optional[str] = Query(None, description="Estado de transacción (opcional)"),
    agent_id: Optional[str] = Query(None, description="Filtra por asesor (UUID, opcional)"),
    tag_ids: Optional[list[str]] = Query(None, description="Una o más etiquetas (OR)"),
):
    """Agregados coordinados para el panel operativo unificado."""
    return await use_case.execute(
        corridor=corridor,
        date_from=date_from,
        date_to=date_to,
        granularity=granularity,
        status=status,
        agent_id=agent_id,
        tag_ids=tag_ids,
    )


@router.get(
    "/weekly",
    response_model=WeeklyMetricsDTO,
    dependencies=[Depends(require_permission("metrics.view"))],
)
async def weekly_metrics(
    use_case: GetWeeklyMetricsUseCaseDep,
    origin_currency: str = Query(..., description="Moneda de origen (PEN|BRL|USD)"),
    destination_currency: str = Query(..., description="Moneda de destino (PEN|BRL|USD)"),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD (opcional)"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD (opcional)"),
    granularity: Optional[str] = Query("week", description="day | week | month | year"),
    status: Optional[str] = Query(None, description="Estado de transacción (opcional)"),
    agent_id: Optional[str] = Query(None, description="Filtra por asesor (UUID, opcional)"),
):
    """Métricas por periodo (día/semana/mes) del corredor para el backoffice."""
    return await use_case.execute(
        origin_currency=origin_currency,
        destination_currency=destination_currency,
        date_from=date_from,
        date_to=date_to,
        granularity=granularity,
        status=status,
        agent_id=agent_id,
    )
