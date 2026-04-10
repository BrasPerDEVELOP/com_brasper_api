# app/modules/transactions/infrastructure/repository.py
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.transactions.domain.models import Transaction
from app.modules.transactions.interfaces.transaction_repository import TransactionRepositoryInterface
from app.shared.repositorie_base import BaseAsyncRepository


class SQLAlchemyTransactionRepository(
    BaseAsyncRepository[Transaction], TransactionRepositoryInterface
):
    def __init__(self, db: AsyncSession):
        super().__init__(Transaction, db)

    async def next_sequential_transaction_code(
        self, origin_currency_code: str, destination_currency_code: str
    ) -> str:
        oc = origin_currency_code.upper().strip()
        dc = destination_currency_code.upper().strip()
        prefix = f"{oc}-{dc}-"
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(abs(hashtext(cast(:pfx AS text))))"),
            {"pfx": prefix},
        )
        result = await self.session.execute(
            text(
                """
                SELECT COALESCE(
                    MAX(
                        (substring(t.code FROM ('^' || :pfx || '([0-9]+)$')))::bigint
                    ),
                    0
                )
                FROM transaction.transactions t
                WHERE t.code ~ ('^' || :pfx || '[0-9]+$')
                """
            ),
            {"pfx": prefix},
        )
        n = int(result.scalar_one()) + 1
        return f"{prefix}{n:010d}"
