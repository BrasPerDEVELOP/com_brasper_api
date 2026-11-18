"""Regression: real PDF generation + MIME/SMTP code, with no external delivery."""
from email import policy
from email.parser import BytesParser
from io import BytesIO
import smtplib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pypdf import PdfReader

from app.modules.billing.application.use_cases import DeliverPendingInvoiceEmailsUseCase
from app.modules.billing.infrastructure import invoice_email
from app.modules.billing.infrastructure.branded_pdf import _verification
from app.modules.omie.application import email_delivery as omie_email
from test_billing_branded_pdf import invoice, source_pdf
from test_omie_email import fixture_service


@pytest.fixture
def smtp_stub(monkeypatch):
    connections = []

    def connect(*args, **kwargs):
        smtp = MagicMock()
        smtp.__enter__.return_value = smtp
        smtp.__exit__.return_value = False
        smtp.login.side_effect = connect.auth_error
        connections.append(smtp)
        return smtp

    connect.auth_error = None
    monkeypatch.setattr(invoice_email.smtplib, 'SMTP', connect)
    return connect, connections


def settings():
    return SimpleNamespace(
        SMTP_HOST='smtp.example.test', SMTP_PORT=587,
        SMTP_USERNAME='sender@example.com', SMTP_PASSWORD='test-secret-not-real',
        SMTP_FROM_EMAIL='sender@example.com', SMTP_USE_TLS=True,
        billing_issuer=lambda ruc: SimpleNamespace(display_name='BrasPer'),
    )


def delivery(source=None, ruc='20611936428', name='INGENITECH S.A.C.'):
    record = invoice(ruc=ruc, name=name)
    record.customer_email = 'original@example.com'
    record.email_recipients = ['original@example.com', 'extra@example.com']
    record.email_delivered_to = ['original@example.com']

    async def delivered(invoice_id, recipient):
        record.email_delivered_to.append(recipient)

    repo = SimpleNamespace(
        list_pending_emails=AsyncMock(return_value=[record]),
        claim_invoice_email=AsyncMock(return_value=True),
        get_invoice=AsyncMock(return_value=record),
        get_transaction_for_billing=AsyncMock(return_value=None),
        record_email_delivery=AsyncMock(side_effect=delivered),
        complete_invoice_email=AsyncMock(), add_event=AsyncMock(), commit=AsyncMock(),
    )
    original = source if source is not None else source_pdf()
    storage = SimpleNamespace(read_file=AsyncMock(return_value=(original, 'application/pdf')))
    return DeliverPendingInvoiceEmailsUseCase(repo, None, settings(), storage), record, repo, original


def transmitted_message(connection):
    message = connection.send_message.call_args.args[0]
    return BytesParser(policy=policy.default).parsebytes(message.as_bytes(policy=policy.SMTP))


@pytest.mark.asyncio
@pytest.mark.parametrize('ruc,name', [
    ('20611936428', 'INGENITECH S.A.C.'), ('20608550454', 'BRASPER 21 S.A.C.'),
])
async def test_generated_boleta_is_attached_to_extra_recipient_only(smtp_stub, ruc, name):
    _, connections = smtp_stub
    worker, record, repo, original = delivery(ruc=ruc, name=name)
    assert await worker.execute() == 1
    assert len(connections) == 1
    smtp = connections[0]
    calls = [call[0] for call in smtp.method_calls]
    assert calls == ['ehlo', 'starttls', 'ehlo', 'login', 'send_message']
    message = transmitted_message(smtp)
    assert str(message['To']) == 'extra@example.com'
    assert message['Cc'] is None and message['Bcc'] is None
    assert record.full_number in message['Subject']
    attachments = list(message.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_content_type() == 'application/pdf'
    assert attachments[0].get_filename() == record.file_name + '.pdf'
    pdf = attachments[0].get_payload(decode=True)
    text = '\n'.join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)
    for value in (name, ruc, record.full_number, '59.86', '50.73', '9.13', '001234567'):
        assert value in text
    assert _verification(pdf, record.full_number) == _verification(original, record.full_number)
    assert record.email_delivered_to == ['original@example.com', 'extra@example.com']
    repo.complete_invoice_email.assert_awaited_once_with(record.id, sent=True)


@pytest.mark.asyncio
@pytest.mark.parametrize('error', [
    smtplib.SMTPAuthenticationError(534, b'5.7.14 browser login required private-link-secret'),
    smtplib.SMTPServerDisconnected('private-link-secret'),
])
async def test_gmail_block_then_retry_does_not_resend_previous_recipient(smtp_stub, caplog, error):
    connect, connections = smtp_stub
    worker, record, repo, _ = delivery()
    connect.auth_error = error
    assert await worker.execute() == 0
    connections[0].send_message.assert_not_called()
    repo.record_email_delivery.assert_not_awaited()
    repo.complete_invoice_email.assert_awaited_once_with(record.id, sent=False)
    assert record.email_delivered_to == ['original@example.com']
    assert 'private-link-secret' not in caplog.text
    assert 'test-secret-not-real' not in caplog.text
    assert type(error).__name__ in caplog.text

    # Simulates the operator re-queuing after Google allows authentication.
    connect.auth_error = None
    assert await worker.execute() == 1
    assert transmitted_message(connections[1])['To'] == 'extra@example.com'
    repo.record_email_delivery.assert_awaited_once_with(record.id, 'extra@example.com')
    assert record.email_delivered_to == ['original@example.com', 'extra@example.com']


@pytest.mark.asyncio
@pytest.mark.parametrize('source', [b'<html>Provider error</html>', source_pdf('BB02-00000999')])
async def test_invalid_or_wrong_boleta_never_opens_smtp(smtp_stub, source):
    _, connections = smtp_stub
    worker, record, repo, _ = delivery(source)
    assert await worker.execute() == 0
    assert connections == []
    repo.record_email_delivery.assert_not_awaited()
    repo.complete_invoice_email.assert_awaited_once_with(record.id, sent=False)


@pytest.mark.asyncio
async def test_database_failure_after_send_keeps_claim_for_reconciliation(smtp_stub):
    _, connections = smtp_stub
    worker, _, repo, _ = delivery()
    repo.record_email_delivery.side_effect = RuntimeError('database unavailable')
    assert await worker.execute() == 0
    connections[0].send_message.assert_called_once()
    # Do not mark failed/retryable when SMTP already accepted the message.
    repo.complete_invoice_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_omie_official_pdf_is_preserved_in_email_attachment(smtp_stub, monkeypatch):
    _, connections = smtp_stub
    service, row, repo = fixture_service()
    service.settings = settings()
    row.email_recipients = ['extra@example.com']
    official_pdf = source_pdf('NFS-e 16298')
    monkeypatch.setattr(omie_email, 'download_pdf', AsyncMock(return_value=official_pdf))
    assert await service.deliver_pending() == 1
    message = transmitted_message(connections[0])
    attachment, = message.iter_attachments()
    assert message['To'] == 'extra@example.com'
    assert attachment.get_filename() == 'NFSe-42.pdf'
    assert attachment.get_payload(decode=True) == official_pdf
    repo.delivered.assert_awaited_once_with(row, 'extra@example.com')
    repo.complete.assert_awaited_once_with(row, 'sent')
