# app/modules/metrics/application/use_cases/management_use_cases.py
"""Caso de uso del panel gerencial."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException

from app.modules.coin.domain.enums import Currency
from app.modules.metrics.application.schemas.management_schema import (
    ManagementDashboardDTO,
)
from app.modules.metrics.application.use_cases.metrics_use_cases import VALID_CORRIDORS
from app.modules.metrics.interfaces.management_repository import (
    ManagementRepositoryInterface,
)

MIN_YEAR = 2015
MAX_TOP_LIMIT = 50


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=422, detail=detail)


class GetManagementDashboardUseCase:
    def __init__(self, repo: ManagementRepositoryInterface):
        self.repo = repo

    async def execute(
        self,
        *,
        year: Optional[int] = None,
        corridor: str = "all",
        currency: Optional[str] = None,
        company: Optional[str] = None,
        status: Optional[str] = None,
        top_month: Optional[int] = None,
        top_limit: int = 15,
    ) -> ManagementDashboardDTO:
        today = datetime.now(timezone.utc)
        resolved_year = year or today.year
        if resolved_year < MIN_YEAR or resolved_year > today.year + 1:
            raise _unprocessable(f"year inválido: {year!r}")

        normalized_corridor = (corridor or "all").strip()
        normalized_corridor = (
            "all" if normalized_corridor.lower() == "all" else normalized_corridor.upper()
        )
        if normalized_corridor not in VALID_CORRIDORS:
            raise _unprocessable(f"corridor inválido: {corridor!r}")

        parsed_currency: Optional[Currency] = None
        if currency and currency.strip():
            try:
                parsed_currency = Currency(currency.strip().upper())
            except ValueError:
                raise _unprocessable(f"currency inválida: {currency!r}")

        if top_month is not None and not 1 <= top_month <= 12:
            raise _unprocessable(f"top_month inválido: {top_month!r} (1-12)")

        data = await self.repo.dashboard(
            year=resolved_year,
            corridor=normalized_corridor,
            currency=parsed_currency,
            company=(company or "").strip() or None,
            status=(status or "").strip() or None,
            top_month=top_month,
            top_limit=max(1, min(int(top_limit or 15), MAX_TOP_LIMIT)),
        )
        return ManagementDashboardDTO(**data)
