"""El PDF se envía una sola vez después de que SUNAT acepta el comprobante."""
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.billing.application import use_cases
from app.modules.billing.application.schemas import SendInvoiceEmailCmd


@pytest.mark.asyncio
async def test_delivery_claims_accepted_invoice_once(monkeypatch):
    invoice = SimpleNamespace(
        id=uuid4(), issuer_ruc="20608550454", customer_email="cliente@example.com",
        full_number="BB02-00000001",
    )
    repo = SimpleNamespace(
        list_pending_emails=AsyncMock(return_value=[invoice]),
        claim_invoice_email=AsyncMock(side_effect=[True, False]),
        complete_invoice_email=AsyncMock(), add_event=AsyncMock(), commit=AsyncMock(),
    )
    pdf = AsyncMock(return_value=(b"%PDF-1.7\n", "boleta.pdf"))
    monkeypatch.setattr(use_cases.GetInvoicePdfUseCase, "execute", pdf)
    sent = []
    monkeypatch.setattr(use_cases, "send_invoice_pdf", lambda *args, **kwargs: sent.append(kwargs))
    settings = SimpleNamespace(billing_issuer=lambda ruc: SimpleNamespace(display_name="BRASPER 21 S.A.C."))
    delivery = use_cases.DeliverPendingInvoiceEmailsUseCase(repo, None, settings)

    assert await delivery.execute() == 1
    assert len(sent) == 1
    assert sent[0]["recipient"] == "cliente@example.com"
    repo.complete_invoice_email.assert_awaited_once_with(invoice.id, sent=True)
    assert await delivery.execute() == 0
    assert len(sent) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('explicit,expected', [(None, 'cliente@example.com'), (' nuevo@example.com ', 'nuevo@example.com')])
async def test_email_request_uses_default_or_edited_recipient(monkeypatch, explicit, expected):
    invoice = SimpleNamespace(id=uuid4(), transaction_id=uuid4(), status='accepted',
                              environment='production', customer_email='cliente@example.com')
    repo = SimpleNamespace(get_invoice=AsyncMock(return_value=invoice),
                           queue_invoice_email=AsyncMock(return_value=True),
                           add_event=AsyncMock(), commit=AsyncMock(), refresh=AsyncMock())
    settings = SimpleNamespace(BILLING_ENABLED=True, APISUNAT_ENVIRONMENT='production',
                               SMTP_HOST='smtp.example.com', SMTP_USERNAME='test', SMTP_PASSWORD='test',
                               SMTP_FROM_EMAIL='emisor@example.com', SMTP_USE_TLS=True)
    monkeypatch.setattr(use_cases.InvoiceDTO, 'from_entity', lambda entity: entity)
    await use_cases.RequestInvoiceEmailUseCase(repo, settings).execute(
        invoice.id, SendInvoiceEmailCmd(customer_email=explicit))
    repo.queue_invoice_email.assert_awaited_once_with(invoice.id, expected)
    repo.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_email_request_rejects_unaccepted_invoice():
    invoice = SimpleNamespace(status='sent')
    repo = SimpleNamespace(get_invoice=AsyncMock(return_value=invoice), queue_invoice_email=AsyncMock())
    settings = SimpleNamespace(BILLING_ENABLED=True)
    with pytest.raises(ValueError, match='acepte'):
        await use_cases.RequestInvoiceEmailUseCase(repo, settings).execute(uuid4(), SendInvoiceEmailCmd())
    repo.queue_invoice_email.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('recipient', ['', 'no-es-correo'])
async def test_email_request_rejects_invalid_address_before_queue(recipient):
    invoice = SimpleNamespace(status='accepted', environment='production')
    repo = SimpleNamespace(get_invoice=AsyncMock(return_value=invoice), queue_invoice_email=AsyncMock())
    settings = SimpleNamespace(BILLING_ENABLED=True, APISUNAT_ENVIRONMENT='production')
    with pytest.raises(ValueError, match='correo'):
        await use_cases.RequestInvoiceEmailUseCase(repo, settings).execute(
            uuid4(), SendInvoiceEmailCmd(customer_email=recipient))
    repo.queue_invoice_email.assert_not_awaited()


def test_description_uses_transaction_company():
    settings = SimpleNamespace(BILLING_ITEM_DESCRIPTION='Comisión por operación {code}')
    transaction = SimpleNamespace(code='PxB-001832', company_name='INGENITECH S.A.C.')
    assert use_cases.invoice_item_description(settings, transaction) == (
        'Comisión por operación PxB-001832. Razón social: INGENITECH S.A.C.')
