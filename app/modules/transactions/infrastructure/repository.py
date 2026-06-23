# app/modules/transactions/infrastructure/repository.py
from __future__ import annotations

from typing import List, Sequence, Union

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination.offset import PageParams, PaginatedResult
from app.modules.coin.domain.enums import Currency
from app.modules.coin.domain.models import TaxRate
from app.modules.transactions.domain.models import Transaction
from app.modules.transactions.interfaces.transaction_repository import TransactionRepositoryInterface
from app.shared.query_filter import QueryFilter
from app.shared.repositorie_base import BaseAsyncRepository


def compact_currency_pair_prefix(origin_currency_code: str, destination_currency_code: str) -> str:
    """Prefijo de código: primera letra de origen + 'x' + primera letra de destino + '-'.
    Ej.: PEN→BRL => PxB-, BRL→PEN => BxP-, USD→BRL => UxB-.
    """
    oc = origin_currency_code.upper().strip()
    dc = destination_currency_code.upper().strip()
    if not oc or not dc:
        raise ValueError("Los códigos de moneda origen y destino son obligatorios")
    return f"{oc[0]}x{dc[0]}-"


class SQLAlchemyTransactionRepository(
    BaseAsyncRepository[Transaction], TransactionRepositoryInterface
):
    def __init__(self, db: AsyncSession):
        super().__init__(Transaction, db)

    async def list(
        self,
        query_filter: QueryFilter | None = None,
        eager_options: Sequence | None = None,
        default_sort_direction: str = "desc",
        limit: int | None = None,
        offset: int | None = None,
        *,
        currency: Currency | None = None,
        origin_currency: Currency | None = None,
        destination_currency: Currency | None = None,
    ) -> Union[List[Transaction], PaginatedResult[Transaction]]:
        if currency is None and origin_currency is None and destination_currency is None:
            return await super().list(
                query_filter=query_filter,
                eager_options=eager_options,
                default_sort_direction=default_sort_direction,
                limit=limit,
                offset=offset,
            )
        return await self._list_by_currency(
            query_filter=query_filter,
            eager_options=eager_options,
            default_sort_direction=default_sort_direction,
            limit=limit,
            offset=offset,
            currency=currency,
            origin_currency=origin_currency,
            destination_currency=destination_currency,
        )

    async def _list_by_currency(
        self,
        *,
        query_filter: QueryFilter | None,
        eager_options: Sequence | None,
        default_sort_direction: str,
        limit: int | None,
        offset: int | None,
        currency: Currency | None,
        origin_currency: Currency | None,
        destination_currency: Currency | None,
    ) -> Union[List[Transaction], PaginatedResult[Transaction]]:
        if query_filter is None:
            query_filter = QueryFilter()

        has_pagination = limit is not None or offset is not None
        if has_pagination:
            query_filter.pagination = PageParams(skip=offset or 0, limit=limit or 20)
            query_filter.pagination.validate_limit()

        if eager_options:
            existing_options = query_filter.eager_options or []
            query_filter.eager_options = existing_options + list(eager_options)

        if not query_filter.order_by and hasattr(self.model, "created_at"):
            query_filter.order_by = [("created_at", default_sort_direction)]

        stmt = (
            select(Transaction)
            .join(TaxRate, Transaction.tax_rate_id == TaxRate.id)
            .where(TaxRate.deleted.is_(False))
        )
        if currency is not None:
            stmt = stmt.where(
                or_(TaxRate.coin_a == currency, TaxRate.coin_b == currency)
            )
        if origin_currency is not None:
            stmt = stmt.where(TaxRate.coin_a == origin_currency)
        if destination_currency is not None:
            stmt = stmt.where(TaxRate.coin_b == destination_currency)

        stmt = query_filter.apply(stmt, Transaction)

        if query_filter.eager_options:
            stmt = stmt.options(*query_filter.eager_options)

        if has_pagination:
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total_result = await self.session.execute(count_stmt)
            total = total_result.scalar_one()
            stmt = stmt.offset(query_filter.pagination.skip).limit(query_filter.pagination.limit)
            result = await self.session.execute(stmt)
            items = (
                result.unique().scalars().all()
                if query_filter.eager_options
                else result.scalars().all()
            )
            skip = query_filter.pagination.skip
            page_limit = query_filter.pagination.limit
            return PaginatedResult(
                total=total,
                items=items,
                skip=skip,
                limit=page_limit,
                has_next=skip + page_limit < total,
                has_previous=skip > 0,
            )

        if query_filter.pagination:
            stmt = stmt.offset(query_filter.pagination.skip).limit(query_filter.pagination.limit)

        result = await self.session.execute(stmt)
        if query_filter.eager_options:
            return result.unique().scalars().all()
        return result.scalars().all()

    async def next_sequential_transaction_code(
        self, origin_currency_code: str, destination_currency_code: str
    ) -> str:
        prefix = compact_currency_pair_prefix(origin_currency_code, destination_currency_code)
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
