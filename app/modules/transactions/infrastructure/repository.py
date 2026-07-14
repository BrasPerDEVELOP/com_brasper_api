# app/modules/transactions/infrastructure/repository.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Sequence, Union
from uuid import UUID

from sqlalchemy import String, and_, cast, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination.offset import PageParams, PaginatedResult
from app.modules.coin.domain.enums import Currency
from app.modules.coin.domain.models import TaxRate
from app.modules.transactions.domain.enums import TransactionStatus
from app.modules.transactions.domain.models import Transaction, TransactionDestination
from app.modules.transactions.interfaces.transaction_repository import TransactionRepositoryInterface
from app.shared.query_filter import QueryFilter
from app.shared.repositorie_base import BaseAsyncRepository


def _effective_status_condition(value: str):
    """Traduce un estado "de presentación" a la condición SQL equivalente.

    Refleja la lógica del frontend (``resolveTransactionStatusForDisplay``):
    una transacción en ``verification`` con ``checked=True`` se muestra como
    ``verified``; ``checked`` es equivalente a ``verified``.
    Devuelve ``None`` si el valor no es un estado reconocido.
    """
    v = (value or "").strip().lower()
    if not v:
        return None
    if v in ("verified", "checked"):
        return or_(
            Transaction.status.in_([TransactionStatus.verified, TransactionStatus.checked]),
            and_(Transaction.status == TransactionStatus.verification, Transaction.checked.is_(True)),
        )
    if v == "verification":
        return and_(
            Transaction.status == TransactionStatus.verification,
            Transaction.checked.is_(False),
        )
    try:
        return Transaction.status == TransactionStatus(v)
    except ValueError:
        return None


def _search_condition(term: str):
    """Búsqueda de texto libre sobre ``code``, ``operation_number`` e ``id``."""
    pattern = f"%{term.strip()}%"
    return or_(
        Transaction.code.ilike(pattern),
        Transaction.operation_number.ilike(pattern),
        cast(Transaction.id, String).ilike(pattern),
    )


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
        search: str | None = None,
        effective_status: str | None = None,
        send_date_from: datetime | None = None,
        send_date_to: datetime | None = None,
        bank_account_id: UUID | None = None,
    ) -> Union[List[Transaction], PaginatedResult[Transaction]]:
        needs_custom = any(
            v is not None
            for v in (
                currency,
                origin_currency,
                destination_currency,
                search,
                effective_status,
                send_date_from,
                send_date_to,
                bank_account_id,
            )
        )
        if not needs_custom:
            return await super().list(
                query_filter=query_filter,
                eager_options=eager_options,
                default_sort_direction=default_sort_direction,
                limit=limit,
                offset=offset,
            )
        return await self._list_impl(
            query_filter=query_filter,
            eager_options=eager_options,
            default_sort_direction=default_sort_direction,
            limit=limit,
            offset=offset,
            currency=currency,
            origin_currency=origin_currency,
            destination_currency=destination_currency,
            search=search,
            effective_status=effective_status,
            send_date_from=send_date_from,
            send_date_to=send_date_to,
            bank_account_id=bank_account_id,
        )

    async def _list_impl(
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
        search: str | None,
        effective_status: str | None,
        send_date_from: datetime | None,
        send_date_to: datetime | None,
        bank_account_id: UUID | None,
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

        needs_tax_join = (
            currency is not None
            or origin_currency is not None
            or destination_currency is not None
        )
        stmt = select(Transaction)
        if needs_tax_join:
            stmt = stmt.join(TaxRate, Transaction.tax_rate_id == TaxRate.id).where(
                TaxRate.deleted.is_(False)
            )
        if currency is not None:
            stmt = stmt.where(
                or_(TaxRate.coin_a == currency, TaxRate.coin_b == currency)
            )
        if origin_currency is not None:
            stmt = stmt.where(TaxRate.coin_a == origin_currency)
        if destination_currency is not None:
            stmt = stmt.where(TaxRate.coin_b == destination_currency)

        if search and search.strip():
            stmt = stmt.where(_search_condition(search))

        if effective_status:
            status_cond = _effective_status_condition(effective_status)
            if status_cond is not None:
                stmt = stmt.where(status_cond)

        if send_date_from is not None:
            stmt = stmt.where(Transaction.send_date >= send_date_from)
        if send_date_to is not None:
            stmt = stmt.where(Transaction.send_date <= send_date_to)

        if bank_account_id is not None:
            stmt = stmt.where(
                or_(
                    Transaction.bank_account_origin_id == bank_account_id,
                    Transaction.bank_account_destination_id == bank_account_id,
                    Transaction.destinations.any(
                        TransactionDestination.bank_account_id == bank_account_id
                    ),
                )
            )

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

    # Estados considerados "volumen" (operaciones cerradas/verificadas de caja).
    _VOLUME_STATUSES = (TransactionStatus.completed, TransactionStatus.checked)

    async def metrics(self) -> dict:
        """Agregados globales para el dashboard (sobre todas las transacciones).

        Devuelve conteo por estado, total, volumen (origen/destino) de los
        estados de volumen y el conteo de los últimos 7 días.
        """
        base = Transaction.deleted.is_(False)

        # Conteo por estado (y total derivado).
        status_rows = await self.session.execute(
            select(Transaction.status, func.count())
            .where(base)
            .group_by(Transaction.status)
        )
        by_status: dict[str, int] = {}
        total = 0
        for status_value, count in status_rows.all():
            key = status_value.value if hasattr(status_value, "value") else str(status_value)
            by_status[key] = count
            total += count

        # Volumen (sumas) de los estados de volumen.
        volume_row = await self.session.execute(
            select(
                func.coalesce(func.sum(Transaction.origin_amount), 0),
                func.coalesce(func.sum(Transaction.destination_amount), 0),
            ).where(base, Transaction.status.in_(self._VOLUME_STATUSES))
        )
        volume_origin, volume_destination = volume_row.one()

        # Conteo de los últimos 7 días (por created_at).
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        last_7_days = (
            await self.session.execute(
                select(func.count()).where(base, Transaction.created_at >= cutoff)
            )
        ).scalar_one()

        return {
            "total": total,
            "by_status": by_status,
            "volume_origin": float(volume_origin or 0),
            "volume_destination": float(volume_destination or 0),
            "last_7_days": last_7_days,
        }

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
