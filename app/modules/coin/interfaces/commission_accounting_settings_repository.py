from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from app.modules.coin.domain.models import CommissionAccountingSettings
from app.shared.repositorie_base import BaseAsyncRepository


class CommissionAccountingSettingsRepositoryInterface(ABC):
    """Puerto de persistencia para el singleton de settings contables."""

    @abstractmethod
    async def get_current(self) -> Optional[CommissionAccountingSettings]:
        raise NotImplementedError

    @abstractmethod
    async def add(self, entity: CommissionAccountingSettings) -> CommissionAccountingSettings:
        raise NotImplementedError

    @abstractmethod
    async def update(self, entity: CommissionAccountingSettings) -> CommissionAccountingSettings:
        raise NotImplementedError

    @abstractmethod
    async def commit(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def refresh(self, entity: CommissionAccountingSettings) -> None:
        raise NotImplementedError
