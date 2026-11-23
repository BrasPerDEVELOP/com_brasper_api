from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.billing.application.use_cases import IssueInvoiceUseCase, PreviewInvoiceUseCase, prepare_issue
from app.modules.omie.application.service import OmieBillingService
from app.modules.transactions.domain.enums import TransactionStatus
from test_billing_use_cases import FakeRepo, FakeClient, _transaction, _settings


@pytest.mark.asyncio
async def test_sunat_dated_without_invoice_blocks_preview_and_direct_issue_before_reserving():
    tx = _transaction()
    tx.billing_date = datetime.now(timezone.utc)
    repo, client = FakeRepo(tx), FakeClient()
    preview = await PreviewInvoiceUseCase(repo, _settings()).execute(tx.id)
    assert preview.can_issue is False
    assert 'fecha de facturación' in preview.reason
    with pytest.raises(ValueError, match='fecha de facturación'):
        await IssueInvoiceUseCase(repo, client, _settings()).execute(tx.id)
    assert repo.series == {} and repo.invoices == [] and repo.commits == 0
    assert client.sent == []


@pytest.mark.asyncio
async def test_sunat_existing_history_keeps_reissue_rules_after_voiding():
    tx = _transaction()
    tx.billing_date = datetime.now(timezone.utc)
    repo = FakeRepo(tx)
    repo.get_latest_invoice = AsyncMock(return_value=SimpleNamespace(status='voided'))
    assert (await prepare_issue(repo, _settings(), tx.id)).transaction is tx


@pytest.mark.asyncio
async def test_sunat_without_billing_date_remains_available():
    tx = _transaction()
    tx.billing_date = None
    assert (await PreviewInvoiceUseCase(FakeRepo(tx), _settings()).execute(tx.id)).can_issue


def omie_service(record=None):
    tx = SimpleNamespace(id=uuid4(), billing_date=datetime.now(timezone.utc),
                         status=TransactionStatus.completed, tax_rate_id=uuid4())
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: tx)),
                         get=AsyncMock(return_value=record), add=lambda row: pytest.fail('must not reserve'), commit=AsyncMock())
    client = SimpleNamespace(call=AsyncMock())
    svc = OmieBillingService(db, SimpleNamespace(OMIE_ENABLED=True), client)
    svc.billing = SimpleNamespace(get_tax_rate=AsyncMock(return_value=SimpleNamespace(coin_a='brl', coin_b='pen')),
                                  get_open_invoice=AsyncMock(return_value=None),
                                  get_final_sale_for_billing=AsyncMock(return_value=Decimal('10')))
    return svc, tx, db, client


@pytest.mark.asyncio
async def test_omie_dated_without_note_blocks_preview_and_direct_issue_before_remote_calls():
    svc, tx, db, client = omie_service()
    with pytest.raises(ValueError, match='fecha de facturación'):
        await svc.preview(tx.id)
    with pytest.raises(ValueError, match='fecha de facturación'):
        await svc.issue(tx.id, Decimal('10'), '12345678901')
    client.call.assert_not_awaited()
    db.commit.assert_not_awaited()
    svc.billing.get_final_sale_for_billing.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['pending', 'issued', 'review_required', 'cancelled'])
async def test_omie_existing_note_stays_consultable_despite_date(status):
    record = SimpleNamespace(status=status, total=Decimal('10'), os_id=123, nfse_number='42', error=None, snapshot={})
    svc, tx, _, client = omie_service(record)
    result = await svc.preview(tx.id)
    assert result['record']['status'] == status
    assert result['can_issue'] is False
    client.call.assert_not_awaited()
