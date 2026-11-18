from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.omie.application.description import service_description, saved_description
from app.modules.omie.application.service import OmieBillingService, build_order


@pytest.mark.parametrize('destination', ['pen', 'usd'])
def test_description_uses_remittance_amounts_and_currency_not_commission(destination):
    tx = SimpleNamespace(code='BxP-0000002747', origin_amount=Decimal('1234.56'), destination_amount=Decimal('987.65'))
    text = service_description(tx, SimpleNamespace(coin_a='brl', coin_b=destination), 'Remessa internacional')
    assert text == f'Remessa internacional\nOperação Brasper: BxP-0000002747\nValor enviado: BRL 1.234,56\nValor a receber: {destination.upper()} 987,65'
    order = build_order(uuid4(), tx.code, 1, 2, 3, '1.01.02', Decimal('13.31'), text)
    assert order['ServicosPrestados'][0]['cDescServ'] == text
    assert order['ServicosPrestados'][0]['nValUnit'] == 13.31
    assert 'impostos' not in order['ServicosPrestados'][0]


@pytest.mark.parametrize('value', [None, 'NaN', 'Infinity', '0', '-1'])
def test_missing_or_invalid_remittance_amount_never_produces_fiscal_text(value):
    with pytest.raises(ValueError, match='montos'):
        service_description(SimpleNamespace(code='BxP-1', origin_amount=value, destination_amount=10), SimpleNamespace(coin_a='brl', coin_b='pen'), '')


def test_history_only_uses_saved_description_and_does_not_invent_old_note_text():
    assert saved_description({'service': 'Remessa internacional', 'order': {'ServicosPrestados': [{'nCodServico': 1}]}}) == ''
    assert saved_description({'description': 'preview', 'order': {'ServicosPrestados': [{'cDescServ': 'sent text'}]}}) == 'sent text'
    assert saved_description(None) == ''


@pytest.mark.asyncio
async def test_changed_description_blocks_emission_before_any_write():
    db = SimpleNamespace(add=lambda row: pytest.fail('Should not reserve'), commit=AsyncMock())
    client = SimpleNamespace(call=AsyncMock())
    service = OmieBillingService(db, SimpleNamespace(), client)
    service.preview = AsyncMock(return_value={'can_issue': True, 'total': '13.31', 'document': '12345678901', 'description': 'new amounts'})
    with pytest.raises(ValueError, match='detalle'):
        await service.issue(uuid4(), Decimal('13.31'), '12345678901', 'old amounts')
    client.call.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_reserved_snapshot_and_incluir_os_keep_the_exact_preview_description():
    text = 'Remessa internacional\nOperação Brasper: BxP-1\nValor enviado: BRL 200,00\nValor a receber: PEN 115,00'
    tx_id = uuid4()
    order = build_order(tx_id, 'BxP-1', 1, 2, 3, '1.01.02', Decimal('9.60'), text)
    stored = []
    db = SimpleNamespace(add=stored.append, commit=AsyncMock())
    async def call(method, payload):
        assert db.commit.await_count >= 1
        if method == 'IncluirOS':
            assert payload['ServicosPrestados'][0]['cDescServ'] == text
            assert stored[0].snapshot['description'] == text
        return {'nCodOS': 42, 'cCodStatus': '0'}
    service = OmieBillingService(db, SimpleNamespace(), SimpleNamespace(call=call))
    service.preview = AsyncMock(return_value={'can_issue': True, 'total': '9.60', 'document': '12345678901', 'description': text, '_order': order})
    result = await service.issue(tx_id, Decimal('9.60'), '12345678901', text)
    assert result['status'] == 'pending'
    assert saved_description(stored[0].snapshot) == text
