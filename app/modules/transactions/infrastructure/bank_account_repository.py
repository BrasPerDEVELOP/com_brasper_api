from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.transactions.domain.models import BankAccount
from app.modules.transactions.interfaces.bank_account_repository import BankAccountRepositoryInterface
from app.shared.repositorie_base import BaseAsyncRepository


class SQLAlchemyBankAccountRepository(
    BaseAsyncRepository[BankAccount], BankAccountRepositoryInterface
):
    def __init__(self, db: AsyncSession):
        super().__init__(BankAccount, db)
