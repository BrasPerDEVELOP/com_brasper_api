# app/modules/metrics/application/schemas/metrics_schema.py
"""DTOs del panel de métricas semanales.

El contrato (snake_case) es el que consume el frontend en
``src/modules/metrics`` del backoffice.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class WeeklyMetricPointDTO(BaseModel):
    """Métricas consolidadas de un periodo (``period_start`` = inicio del bucket)."""

    period_start: str  # ISO date (YYYY-MM-DD)
    envios_count: int
    envios_volume_origin: float
    clientes_nuevos: int
    caja_origin_in: float
    caja_destination_out: float
    caja_diferencia: float
    facturado_destino: float


class WeeklyMetricsTotalsDTO(BaseModel):
    """Totales del rango completo."""

    envios_count: int
    envios_volume_origin: float
    clientes_nuevos: int
    caja_origin_in: float
    caja_destination_out: float
    caja_diferencia: float
    facturado_destino: float


class MetricsRangeDTO(BaseModel):
    """Rango y corredor efectivos devueltos por la API."""

    date_from: str
    date_to: str
    origin_currency: Optional[str] = None
    destination_currency: Optional[str] = None
    corridor: str
    granularity: str = "week"


class WeeklyMetricsDTO(BaseModel):
    """Respuesta consolidada del panel (una sola llamada)."""

    range: MetricsRangeDTO
    weeks: list[WeeklyMetricPointDTO]
    totals: WeeklyMetricsTotalsDTO
