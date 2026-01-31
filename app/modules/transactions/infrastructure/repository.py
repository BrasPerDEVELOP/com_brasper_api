# app/modules/transactions/infrastructure/repository.py
from __future__ import annotations

from uuid import UUID
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.transactions.domain.models import Transaction
from app.modules.transactions.interfaces.transaction_repository import TransactionRepositoryInterface
from app.shared.repositorie_base import BaseAsyncRepository


class SQLAlchemyTransactionRepository(
    BaseAsyncRepository[Transaction], TransactionRepositoryInterface
):
    def __init__(self, db: AsyncSession):
        super().__init__(Transaction, db)
