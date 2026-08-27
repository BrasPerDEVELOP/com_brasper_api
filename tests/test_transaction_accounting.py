"""Tests del listado contable: ``GET /transactions/accounting``.

Cubren el "descuento variable" (`accounting_percentage`): que el caso de uso lo
adjunte a cada ítem, que no se cuele en el listado normal, y que la consulta que
lo resuelve use la convención de rango de `coin.commission_accounting`
(``min_amount <= origin_amount < max_amount``, corte superior exclusivo).
"""
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.core.pagination.offset import PaginatedResult
from app.modules.transactions.application.use_cases.transaction_use_cases import (
    ListTransactionsAccountingUseCase,
    ListTransactionsUseCase,
)
from app.modules.transactions.domain.enums import TransactionStatus


def _transaction_row(**overrides) -> dict:
    """Fila mínima que satisface ``TransactionReadDTO``."""
    now = datetime.now(timezone.utc)
    row = {
        "id": uuid4(),
        "bank_account_destination_id": uuid4(),
        "user_id": uuid4(),
        "tax_rate_id": uuid4(),
        "commission_id": uuid4(),
        "status": "verification",
        "origin_amount": 500.0,
        "destination_amount": 400.0,
        "code": "PxB-0000000001",
        "created_at": now,
        "updated_at": now,
    }
    row.update(overrides)
    return row


class _FakeRepo:
    """Repositorio de listado con porcentajes precargados por id."""

    def __init__(self, rows: list[dict], percentages: dict[UUID, float] | None = None):
        self._rows = rows
        self._percentages = percentages or {}
        self.accounting_calls: list[list[UUID]] = []
        self.list_calls: list[dict] = []

    async def list(self, **kwargs):
        self.list_calls.append(kwargs)
        return PaginatedResult(
            total=len(self._rows),
            items=self._rows,
            skip=0,
            limit=20,
            has_next=False,
            has_previous=False,
        )

    async def accounting_percentages(self, transaction_ids):
        ids = list(transaction_ids)
        self.accounting_calls.append(ids)
        return {i: self._percentages[i] for i in ids if i in self._percentages}


@pytest.mark.asyncio
async def test_accounting_list_attaches_percentage_to_each_item():
    with_bracket = _transaction_row(origin_amount=500.0)
    without_bracket = _transaction_row(origin_amount=50.0)
    repo = _FakeRepo(
        [with_bracket, without_bracket],
        percentages={with_bracket["id"]: 45.0},
    )

    page = await ListTransactionsAccountingUseCase(repo).execute(limit=20, skip=0)

    by_id = {item.id: item for item in page.items}
    assert by_id[with_bracket["id"]].accounting_percentage == 45.0
    # Sin tramo que cubra el monto se queda en None, no en 0.
    assert by_id[without_bracket["id"]].accounting_percentage is None


@pytest.mark.asyncio
async def test_accounting_list_resolves_percentages_in_a_single_query():
    rows = [_transaction_row() for _ in range(3)]
    repo = _FakeRepo(rows, percentages={row["id"]: 60.0 for row in rows})

    await ListTransactionsAccountingUseCase(repo).execute(limit=20, skip=0)

    assert len(repo.accounting_calls) == 1
    assert repo.accounting_calls[0] == [row["id"] for row in rows]


@pytest.mark.asyncio
async def test_empty_page_does_not_query_the_catalog():
    repo = _FakeRepo([])

    page = await ListTransactionsAccountingUseCase(repo).execute(limit=20, skip=0)

    assert page.items == []
    assert repo.accounting_calls == []


@pytest.mark.asyncio
async def test_accounting_list_includes_user_document_from_the_backend():
    row = _transaction_row()
    row["user"] = {
        "id": row["user_id"],
        "role": "client",
        "document_type": "dni",
        "document_number": "12345678",
    }
    repo = _FakeRepo([row])

    page = await ListTransactionsAccountingUseCase(repo).execute(limit=20, skip=0)

    assert page.items[0].user.document_type == "dni"
    assert page.items[0].user.document_number == "12345678"


@pytest.mark.asyncio
async def test_accounting_list_uses_primary_identification_when_user_columns_are_empty():
    row = _transaction_row()
    row["user"] = {
        "id": row["user_id"],
        "role": "client",
        "document_type": None,
        "document_number": None,
        "identifications": [
            {
                "document_type": "cpf",
                "document_number": "39053344705",
                "is_primary": True,
            }
        ],
    }
    repo = _FakeRepo([row])

    page = await ListTransactionsAccountingUseCase(repo).execute(limit=20, skip=0)

    assert page.items[0].user.document_type == "cpf"
    assert page.items[0].user.document_number == "39053344705"


@pytest.mark.asyncio
async def test_accounting_list_leaves_user_document_empty_when_the_client_has_none():
    repo = _FakeRepo([_transaction_row()])

    page = await ListTransactionsAccountingUseCase(repo).execute(limit=20, skip=0)

    assert page.items[0].user.document_type is None
    assert page.items[0].user.document_number is None


@pytest.mark.asyncio
async def test_accounting_list_always_filters_completed_on_the_backend():
    """Contabilidad no lista Verificado ni otros estados, aunque el cliente los pida."""
    repo = _FakeRepo([_transaction_row()])

    await ListTransactionsAccountingUseCase(repo).execute(
        limit=20, skip=0, status=TransactionStatus.verified
    )

    assert repo.list_calls[0]["effective_status"] == TransactionStatus.completed.value


@pytest.mark.asyncio
async def test_accounting_list_filters_completed_when_status_is_omitted():
    repo = _FakeRepo([_transaction_row()])

    await ListTransactionsAccountingUseCase(repo).execute(limit=20, skip=0)

    assert repo.list_calls[0]["effective_status"] == TransactionStatus.completed.value


@pytest.mark.asyncio
async def test_plain_list_does_not_expose_accounting_fields():
    row = _transaction_row()
    repo = _FakeRepo([row], percentages={row["id"]: 45.0})

    page = await ListTransactionsUseCase(repo).execute(limit=20, skip=0)

    assert repo.accounting_calls == []
    assert not hasattr(page.items[0], "accounting_percentage")


class _CapturingSession:
    """Sesión que solo guarda el statement compilado, sin base de datos."""

    def __init__(self):
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)

        class _EmptyResult:
            @staticmethod
            def all():
                return []

        return _EmptyResult()


async def _capture_accounting_sql(transaction_ids) -> str:
    from app.modules.transactions.infrastructure.repository import (
        SQLAlchemyTransactionRepository,
    )

    session = _CapturingSession()
    await SQLAlchemyTransactionRepository(session).accounting_percentages(transaction_ids)
    if not session.statements:
        return ""
    return str(
        session.statements[0].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


@pytest.mark.asyncio
async def test_bracket_query_uses_exclusive_upper_bound():
    """El corte superior es exclusivo: 300 cae en el tramo del 45%, no en el del 40%.

    Es la convención que fijó la migración 069 y que reusa la 072 al vincular
    `commission_accounting_id`; `coin.commission` usa la inclusiva y por eso no
    se puede reutilizar aquí.
    """
    sql = await _capture_accounting_sql([uuid4()])

    assert "origin_amount >= coin.commission_accounting.min_amount" in sql
    assert "origin_amount < coin.commission_accounting.max_amount" in sql
    # El tramo se busca por el par de monedas de la tasa de la transacción.
    assert "coin.commission_accounting.coin_a = coin.tax_rate.coin_a" in sql
    assert "coin.commission_accounting.coin_b = coin.tax_rate.coin_b" in sql
    # Tramos borrados fuera, y un solo tramo por transacción.
    assert "coin.commission_accounting.deleted IS false" in sql
    assert "LIMIT 1" in sql


@pytest.mark.asyncio
async def test_no_ids_skips_the_query_entirely():
    assert await _capture_accounting_sql([]) == ""
    assert await _capture_accounting_sql([None]) == ""
