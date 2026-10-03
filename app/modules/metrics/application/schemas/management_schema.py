# app/modules/metrics/application/schemas/management_schema.py
"""DTOs del panel gerencial (``GET /metrics/management``).

Replica las hojas del Excel de gerencia: envíos, clientes y montos por mes
de un año. Contrato snake_case consumido por ``src/modules/gerencia`` del
backoffice.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ManagementRangeDTO(BaseModel):
    year: int
    date_from: str
    date_to: str
    corridor: str
    currency: Optional[str] = None
    company: Optional[str] = None
    status: Optional[str] = None


class ManagementMonthDTO(BaseModel):
    """Agregados de un mes (``period_start`` = día 1 del mes, ISO date)."""

    period_start: str
    envios_count: int
    envios_by_currency: dict[str, int]
    envios_by_company: dict[str, int]
    active_clients: int
    new_clients: int
    volume_origin: dict[str, float]
    # Comisión cobrada (ingreso bruto) en moneda de origen.
    commission_origin: dict[str, float]
    # Expresado en soles con la tasa mensual registrada en finance.fx_month_rates.
    # ``None`` cuando falta alguna tasa necesaria para ese mes.
    volume_pen_by_currency: dict[str, Optional[float]]
    volume_pen_total: Optional[float] = None
    revenue_pen: Optional[float] = None
    # Egresos del mes en soles (finance.expenses).
    expenses_pen: float = 0.0
    net_pen: Optional[float] = None


class ManagementFxMissingDTO(BaseModel):
    month: int
    currency: str


class ManagementExpenseCategoryDTO(BaseModel):
    category: str
    amount_pen: float
    share: float


class ManagementTopClientDTO(BaseModel):
    user_id: str
    name: str
    envios_count: int


class ManagementTopClientsDTO(BaseModel):
    month: int
    items: list[ManagementTopClientDTO]


class ManagementTotalsDTO(BaseModel):
    envios_count: int
    active_clients: int
    new_clients: int
    volume_origin: dict[str, float]
    volume_pen_total: Optional[float] = None
    revenue_pen: Optional[float] = None
    expenses_pen: float = 0.0
    net_pen: Optional[float] = None


class ManagementDashboardDTO(BaseModel):
    range: ManagementRangeDTO
    months: list[ManagementMonthDTO]
    # Diciembre del año anterior: necesario para la variación % de enero.
    previous_month: Optional[ManagementMonthDTO] = None
    totals: ManagementTotalsDTO
    companies: list[str]
    top_clients: ManagementTopClientsDTO
    # Meses del año con envíos en una moneda sin tasa registrada.
    fx_missing: list[ManagementFxMissingDTO] = []
    # Egresos por categoría del mes de ``top_clients.month``.
    expenses_by_category: list[ManagementExpenseCategoryDTO] = []
