# app/modules/coin/infrastructure/repository.py
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.coin.domain.models import (
    TaxRate,
    TaxRateTrial,
    Commission,
    CommissionAccounting,
    CommissionAccountingSettings,
    CommissionTrial,
)
from app.modules.coin.interfaces.tax_rate_repository import TaxRateRepositoryInterface
from app.modules.coin.interfaces.tax_rate_trial_repository import TaxRateTrialRepositoryInterface
from app.modules.coin.interfaces.commission_repository import CommissionRepositoryInterface
from app.modules.coin.interfaces.commission_accounting_repository import (
    CommissionAccountingRepositoryInterface,
)
from app.modules.coin.interfaces.commission_accounting_settings_repository import (
    CommissionAccountingSettingsRepositoryInterface,
)
from app.modules.coin.interfaces.commission_trial_repository import CommissionTrialRepositoryInterface
from app.shared.repositorie_base import BaseAsyncRepository


class SQLAlchemyTaxRateRepository(BaseAsyncRepository[TaxRate], TaxRateRepositoryInterface):
    def __init__(self, db: AsyncSession):
        super().__init__(TaxRate, db)


class SQLAlchemyTaxRateTrialRepository(BaseAsyncRepository[TaxRateTrial], TaxRateTrialRepositoryInterface):
    def __init__(self, db: AsyncSession):
        super().__init__(TaxRateTrial, db)


class SQLAlchemyCommissionRepository(BaseAsyncRepository[Commission], CommissionRepositoryInterface):
    def __init__(self, db: AsyncSession):
        super().__init__(Commission, db)


class SQLAlchemyCommissionAccountingRepository(
    BaseAsyncRepository[CommissionAccounting],
    CommissionAccountingRepositoryInterface,
):
    def __init__(self, db: AsyncSession):
        super().__init__(CommissionAccounting, db)


class SQLAlchemyCommissionAccountingSettingsRepository(
    BaseAsyncRepository[CommissionAccountingSettings],
    CommissionAccountingSettingsRepositoryInterface,
):
    def __init__(self, db: AsyncSession):
        super().__init__(CommissionAccountingSettings, db)

    async def get_current(self) -> Optional[CommissionAccountingSettings]:
        stmt = (
            select(CommissionAccountingSettings)
            .where(CommissionAccountingSettings.deleted.is_(False))
            .order_by(CommissionAccountingSettings.created_at.asc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class SQLAlchemyCommissionTrialRepository(
    BaseAsyncRepository[CommissionTrial],
    CommissionTrialRepositoryInterface,
):
    def __init__(self, db: AsyncSession):
        super().__init__(CommissionTrial, db)
