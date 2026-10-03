# app/modules/metrics/interfaces/management_repository.py
"""Puerto del repositorio del panel gerencial."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from app.modules.coin.domain.enums import Currency


class ManagementRepositoryInterface(ABC):
    @abstractmethod
    async def dashboard(
        self,
        *,
        year: int,
        corridor: str = "all",
        currency: Optional[Currency] = None,
        company: Optional[str] = None,
        status: Optional[str] = None,
        top_month: Optional[int] = None,
        top_limit: int = 15,
    ) -> dict:
        """Agregados mensuales de ``year`` (más diciembre anterior) y top clientes."""
        raise NotImplementedError
