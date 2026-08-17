# app/modules/coin/infrastructure/repository.py
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.coin.domain.models import (
    TaxRate,
    TaxRateTrial,
    Commission,
    CommissionAccounting,
    CommissionTrial,
)
from app.modules.coin.interfaces.tax_rate_repository import TaxRateRepositoryInterface
from app.modules.coin.interfaces.tax_rate_trial_repository import TaxRateTrialRepositoryInterface
from app.modules.coin.interfaces.commission_repository import CommissionRepositoryInterface
from app.modules.coin.interfaces.commission_accounting_repository import (
    CommissionAccountingRepositoryInterface,
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


class SQLAlchemyCommissionTrialRepository(
    BaseAsyncRepository[CommissionTrial],
    CommissionTrialRepositoryInterface,
):
    def __init__(self, db: AsyncSession):
        super().__init__(CommissionTrial, db)
