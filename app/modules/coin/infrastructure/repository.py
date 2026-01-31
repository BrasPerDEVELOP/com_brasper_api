# app/modules/coin/infrastructure/repository.py
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.coin.domain.models import TaxRate, Commission
from app.modules.coin.interfaces.tax_rate_repository import TaxRateRepositoryInterface
from app.modules.coin.interfaces.commission_repository import CommissionRepositoryInterface
from app.shared.repositorie_base import BaseAsyncRepository


class SQLAlchemyTaxRateRepository(BaseAsyncRepository[TaxRate], TaxRateRepositoryInterface):
    def __init__(self, db: AsyncSession):
        super().__init__(TaxRate, db)


class SQLAlchemyCommissionRepository(BaseAsyncRepository[Commission], CommissionRepositoryInterface):
    def __init__(self, db: AsyncSession):
        super().__init__(Commission, db)
