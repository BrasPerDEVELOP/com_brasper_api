from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.transactions.domain.models import Bank
from app.modules.transactions.interfaces.bank_repository import BankRepositoryInterface
from app.shared.repositorie_base import BaseAsyncRepository


class SQLAlchemyBankRepository(
    BaseAsyncRepository[Bank], BankRepositoryInterface
):
    def __init__(self, db: AsyncSession):
        super().__init__(Bank, db)
