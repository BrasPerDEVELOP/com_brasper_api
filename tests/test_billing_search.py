"""Execute the repository's SQL against isolated rows; never use the real DB."""
import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import sqlite

from app.main import app
from app.modules.billing.adapters.dependencies import list_invoices_uc
from app.modules.billing.application.schemas import InvoiceListDTO
from app.modules.billing.application.use_cases import ListInvoicesUseCase
from app.modules.billing.domain.models import Invoice
from app.modules.billing.infrastructure.repository import SQLAlchemyBillingRepository


class SqlSession:
    def __init__(self, connection):
        self.connection = connection

    async def execute(self, statement):
        sql = str(statement.compile(dialect=sqlite.dialect(), compile_kwargs={'literal_binds': True}))
        cursor = self.connection.execute(sql)
        names = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        return SimpleNamespace(
            scalar_one=lambda: rows[0][0],
            scalars=lambda: SimpleNamespace(all=lambda: [SimpleNamespace(**dict(zip(names, row))) for row in rows]),
        )


@pytest.fixture
def repo():
    connection = sqlite3.connect(':memory:')
    connection.execute("ATTACH DATABASE ':memory:' AS billing")
    # Only the storage types matter here: all ORM-selected columns exist, while
    # unused fiscal values remain NULL. This exercises actual WHERE/ORDER/LIMIT.
    columns = ', '.join(f'"{col.name}" {"INTEGER" if col.name in ("number", "deleted") else "TEXT"}'
                        for col in Invoice.__table__.columns)
    connection.execute(f'CREATE TABLE billing.invoices ({columns})')
    for id_, number, issuer, name, doc, date, deleted, status in [
        ('a', 9, '20611936428', 'MARIA PEREZ', '12345678', '2026-11-18', 0, 'accepted'),
        ('b', 209, '20611936428', 'MARIA PEREZ', '98765432', '2026-11-01', 0, 'accepted'),
        ('c', 10, '20608550454', 'Cliente 100%_real', '55555555', '2026-11-17', 0, 'accepted'),
        ('d', 209, '20608550454', 'OTRO CLIENTE', '00000000', '2026-11-01', 0, 'exception'),
        ('e', 999, '20611936428', 'MARIA PEREZ', '12345678', '2026-11-18', 1, 'accepted'),
    ]:
        connection.execute('INSERT INTO billing.invoices '
            '(id,number,issuer_ruc,customer_name,customer_doc_number,issue_date,deleted,status,series,document_type,file_name) '
            'VALUES (?,?,?,?,?,?,?,?,?,?,?)',
            (id_,number,issuer,name,doc,date,deleted,status,'BB02','03',f'{issuer}-03-BB02-{number:08d}'))
    yield SQLAlchemyBillingRepository(SqlSession(connection))
    connection.close()


@pytest.mark.asyncio
async def test_numeric_code_order_and_stable_pagination_ignore_issue_date(repo):
    first, total = await repo.list_invoices(limit=2)
    second, second_total = await repo.list_invoices(skip=2, limit=2)
    assert total == second_total == 4
    assert [row.id for row in first + second] == ['d', 'b', 'c', 'a']
    assert [row.number for row in first + second] == [209, 209, 10, 9]


@pytest.mark.asyncio
@pytest.mark.parametrize('search,ids', [
    (' bb02-209 ', ['d', 'b']), ('BB02 - 00000209', ['d', 'b']),
    ('BB02-00000209', ['d', 'b']), ('209', ['d', 'b']),
    ('maria perez', ['b', 'a']), ('12345678', ['a']),
    ('%_', ['c']), ('does-not-exist', []), ('   ', ['d', 'b', 'c', 'a']),
])
async def test_search_codes_names_documents_and_literal_wildcards(repo, search, ids):
    rows, total = await repo.list_invoices(search=search)
    assert [row.id for row in rows] == ids
    assert total == len(ids)


@pytest.mark.asyncio
async def test_search_count_is_filtered_before_paginating_and_combines_filters(repo):
    rows, total = await repo.list_invoices(search='maria', skip=1, limit=1,
                                         status='accepted', document_type='03', issuer_ruc='20611936428')
    assert total == 2
    assert [row.number for row in rows] == [9]
    rows, total = await repo.list_invoices(search='BB02-209', issuer_ruc='20608550454', status='accepted')
    assert (rows, total) == ([], 0)


@pytest.mark.asyncio
async def test_use_case_forwards_search_to_repository():
    repo = SimpleNamespace(list_invoices=AsyncMock(return_value=([], 0)))
    await ListInvoicesUseCase(repo).execute(search='BB02-209', skip=10, limit=10)
    assert repo.list_invoices.await_args.kwargs['search'] == 'BB02-209'


def test_http_search_validation_and_pagination():
    uc = SimpleNamespace(execute=AsyncMock(return_value=InvoiceListDTO(items=[], total=0, skip=10, limit=10)))
    app.dependency_overrides[list_invoices_uc] = lambda: uc
    try:
        client = TestClient(app)
        response = client.get('/billing/invoices', params={'search':' BB02-209 ', 'page':2, 'page_size':10})
        assert response.status_code == 200
        assert uc.execute.await_args.kwargs['search'] == 'BB02-209'
        assert uc.execute.await_args.kwargs['skip'] == 10
        response = client.get('/billing/invoices', params={'search':'x'*121})
        assert response.status_code == 422
        assert uc.execute.await_count == 1
    finally:
        app.dependency_overrides.pop(list_invoices_uc, None)
