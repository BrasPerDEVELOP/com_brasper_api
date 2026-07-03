# app/modules/metrics/adapters/dependencies/metrics_dependencies.py
"""Inyección de dependencias del módulo metrics para las rutas."""
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.modules.metrics.application.use_cases import GetWeeklyMetricsUseCase
from app.modules.metrics.infrastructure.repository import SQLAlchemyMetricsRepository
from app.modules.metrics.interfaces.metrics_repository import MetricsRepositoryInterface


def get_metrics_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MetricsRepositoryInterface:
    return SQLAlchemyMetricsRepository(db)


def get_weekly_metrics_uc(
    repo: Annotated[MetricsRepositoryInterface, Depends(get_metrics_repository)],
) -> GetWeeklyMetricsUseCase:
    return GetWeeklyMetricsUseCase(repo)


GetWeeklyMetricsUseCaseDep = Annotated[GetWeeklyMetricsUseCase, Depends(get_weekly_metrics_uc)]
