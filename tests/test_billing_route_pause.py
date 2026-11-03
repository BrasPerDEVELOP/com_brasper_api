from types import SimpleNamespace

import pytest

from app.modules.billing.application.use_cases import (
    IssueInvoiceUseCase, PreviewInvoiceUseCase, RetryInvoiceUseCase, ensure_billing_route_enabled,
)
from app.modules.billing.interfaces.apisunat_client import SendBillResult
from app.modules.coin.domain.enums import Currency
from test_billing_use_cases import FakeRepo, FakeClient, _transaction, _settings


@pytest.mark.asyncio
@pytest.mark.parametrize('destination', [Currency.pen, Currency.usd])
async def test_paused_routes_cannot_preview_issue_or_reserve_number(destination):
    tx = _transaction()
    repo, client = FakeRepo(tx, Currency.brl), FakeClient()
    repo.tax_rate.coin_b = destination
    preview = await PreviewInvoiceUseCase(repo, _settings()).execute(tx.id)
    assert not preview.can_issue and 'temporalmente deshabilitada' in preview.reason
    with pytest.raises(ValueError, match='temporalmente deshabilitada'):
        await IssueInvoiceUseCase(repo, client, _settings()).execute(tx.id)
    assert not repo.series and not repo.invoices and not client.sent


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['error', 'exception', 'rejected'])
async def test_paused_route_cannot_retry_existing_attempt(status):
    tx = _transaction()
    repo, client = FakeRepo(tx), FakeClient()
    client.send_results.append(SendBillResult(status='PENDIENTE', document_id='test-id', raw={}))
    dto = await IssueInvoiceUseCase(repo, client, _settings()).execute(tx.id)
    invoice = await repo.get_invoice(dto.id)
    invoice.status = status
    repo.tax_rate = SimpleNamespace(coin_a=Currency.brl, coin_b=Currency.pen)
    with pytest.raises(ValueError, match='temporalmente deshabilitada'):
        await RetryInvoiceUseCase(repo, client, _settings()).execute(dto.id)
    assert len(client.sent) == 1 and client.find_calls == 0
    assert invoice.status == status


@pytest.mark.parametrize('origin,destination', [('pen', 'brl'), ('usd', 'brl'), ('pen', 'usd'), ('brl', 'brl')])
def test_other_routes_remain_enabled(origin, destination):
    ensure_billing_route_enabled(SimpleNamespace(coin_a=origin, coin_b=destination))
