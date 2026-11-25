import smtplib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import uuid4

import dns.exception
import dns.resolver
import dns.rrset
import pytest

from app.modules.billing.infrastructure import recipient_validation as validation
from app.modules.billing.infrastructure import invoice_email
from app.modules.billing.application import use_cases
from app.modules.billing.application.schemas import SendInvoiceEmailCmd
from app.modules.omie.application import email_delivery
from test_omie_email import fixture_service


def db_with_blocked(addresses=()):
    result = MagicMock()
    result.scalars.return_value.all.return_value = list(addresses)
    return SimpleNamespace(execute=AsyncMock(return_value=result))


def resolver(monkeypatch, value):
    mock = Mock()
    if isinstance(value, Exception):
        mock.resolve.side_effect = value
    else:
        mock.resolve.return_value = dns.rrset.from_text('recipient.org.', 60, 'IN', 'MX', value)
    monkeypatch.setattr(validation, '_resolver', mock)
    return mock


def test_mx_check_preserves_normalized_recipient(monkeypatch):
    mock = resolver(monkeypatch, '10 mx.recipient.org.')
    assert validation.validate_recipient_domain('client@RECIPIENT.ORG') == 'client@recipient.org'
    mock.resolve.assert_called_once_with('recipient.org', 'MX')


@pytest.mark.parametrize('response', [dns.resolver.NXDOMAIN(), '0 .'])
def test_nonexistent_or_null_mx_rejected(monkeypatch, response):
    resolver(monkeypatch, response)
    with pytest.raises(validation.RecipientValidationError, match='dominio reciba'):
        validation.validate_recipient_domain('client@recipient.org')


@pytest.mark.parametrize('response', [dns.exception.Timeout(), dns.resolver.NoNameservers()])
def test_temporary_dns_failure_requests_retry_not_nonexistent_mailbox(monkeypatch, response):
    resolver(monkeypatch, response)
    with pytest.raises(validation.RecipientValidationError, match='nuevamente') as error:
        validation.validate_recipient_domain('client@recipient.org')
    assert not isinstance(error.value, validation.MailboxNotFound)


@pytest.mark.asyncio
async def test_suppressed_recipient_blocks_before_dns(monkeypatch):
    lookup = Mock()
    monkeypatch.setattr(validation, 'validate_recipient_domain', lookup)
    db = db_with_blocked(['client@recipient.org'])
    with pytest.raises(validation.MailboxNotFound):
        await validation.check_invoice_recipients(db, ['CLIENT@recipient.org'])
    lookup.assert_not_called()
    assert db.execute.await_args.args[1]['emails'] == ['client@recipient.org']


@pytest.mark.asyncio
async def test_all_selected_addresses_validated_before_queue(monkeypatch):
    checks=[]
    def check(address):
        checks.append(address)
        if address.startswith('bad@'):
            raise validation.RecipientValidationError('dominio no válido')
    monkeypatch.setattr(validation, 'validate_recipient_domain', check)
    service,row,repo=fixture_service()
    repo.db=db_with_blocked()
    with pytest.raises(validation.RecipientValidationError):
        await service.request(row.transaction_id,['good@recipient.org','bad@recipient.org'])
    assert set(checks)=={'good@recipient.org','bad@recipient.org'}
    repo.queue.assert_not_awaited()
    service.billing.pdf.assert_not_awaited()


@pytest.mark.asyncio
async def test_sunat_request_invalid_domain_never_queues(monkeypatch):
    monkeypatch.setattr(validation,'validate_recipient_domain',Mock(side_effect=validation.RecipientValidationError('dominio no válido')))
    invoice=SimpleNamespace(status='accepted',environment='production',email_delivered_to=[])
    repo=SimpleNamespace(session=db_with_blocked(),get_invoice=AsyncMock(return_value=invoice),queue_invoice_email=AsyncMock())
    settings=SimpleNamespace(BILLING_ENABLED=True,APISUNAT_ENVIRONMENT='production',SMTP_HOST='smtp.example.com',SMTP_USERNAME='test',SMTP_PASSWORD='test',SMTP_FROM_EMAIL='sender@example.com',SMTP_USE_TLS=True)
    with pytest.raises(validation.RecipientValidationError):
        await use_cases.RequestInvoiceEmailUseCase(repo,settings).execute(uuid4(),SendInvoiceEmailCmd(recipients=['bad@recipient.org']))
    repo.queue_invoice_email.assert_not_awaited()


@pytest.mark.parametrize('code,message,blocked', [(550,b'5.1.1 No such user',True),(550,b'5.7.1 Policy rejected',False),(452,b'4.2.2 Quota',False),(535,b'5.7.8 Login failed',False)])
def test_only_definitive_nonexistent_mailbox_is_suppressed(code,message,blocked):
    if blocked:
        with pytest.raises(validation.MailboxNotFound):
            validation.raise_for_invalid_mailbox('client@recipient.org',(code,message))
    else:
        validation.raise_for_invalid_mailbox('client@recipient.org',(code,message))


def test_dns_validation_prevents_smtp_connection(monkeypatch):
    monkeypatch.setattr(invoice_email,'ensure_invoice_email_ready',Mock())
    monkeypatch.setattr(invoice_email,'validate_recipient_domain',Mock(side_effect=validation.RecipientValidationError('Dominio no válido')))
    smtp=Mock()
    monkeypatch.setattr(invoice_email.smtplib,'SMTP',smtp)
    with pytest.raises(validation.RecipientValidationError):
        invoice_email.send_invoice_pdf(SimpleNamespace(),recipient='bad@recipient.org',full_number='BB02-1',issuer_name='TEST',pdf=b'%PDF-1.7',filename='note.pdf')
    smtp.assert_not_called()


@pytest.mark.parametrize('returns_dictionary', [True, False])
def test_smtp_refusal_identifies_the_exact_recipient(monkeypatch, returns_dictionary):
    monkeypatch.setattr(invoice_email,'validate_recipient_domain',lambda address: address)
    connection=MagicMock()
    refused={'client@recipient.org':(550,b'5.1.1 No such user')}
    if returns_dictionary:
        connection.send_message.return_value=refused
    else:
        connection.send_message.side_effect=smtplib.SMTPRecipientsRefused(refused)
    smtp=MagicMock()
    smtp.return_value.__enter__.return_value=connection
    monkeypatch.setattr(invoice_email.smtplib,'SMTP',smtp)
    settings=SimpleNamespace(SMTP_HOST='smtp.example.com',SMTP_PORT=587,SMTP_USERNAME='test',SMTP_PASSWORD='test',SMTP_FROM_EMAIL='sender@example.com',SMTP_USE_TLS=True)
    with pytest.raises(validation.MailboxNotFound) as error:
        invoice_email.send_invoice_pdf(settings,recipient='client@recipient.org',full_number='BB02-1',issuer_name='TEST',pdf=b'%PDF-1.7',filename='note.pdf')
    assert error.value.recipient=='client@recipient.org'
    message=connection.send_message.call_args.args[0]
    assert message['To']=='client@recipient.org'


@pytest.mark.asyncio
@pytest.mark.parametrize('provider',['sunat','omie'])
async def test_worker_revalidates_before_pdf_or_smtp(monkeypatch,provider):
    module=use_cases if provider=='sunat' else email_delivery
    monkeypatch.setattr(module,'check_invoice_recipients',AsyncMock(side_effect=validation.RecipientValidationError('Dominio no válido')))
    sender=Mock()
    monkeypatch.setattr(module,'send_invoice_pdf',sender)
    if provider=='omie':
        service,row,repo=fixture_service()
        row.email_recipients=['bad@recipient.org']
        await service.deliver_pending()
        service.billing.pdf.assert_not_awaited()
        repo.complete.assert_awaited_once_with(row,'failed',error='Dominio no válido')
    else:
        invoice=SimpleNamespace(id=uuid4(),customer_email='bad@recipient.org')
        repo=SimpleNamespace(session=None,list_pending_emails=AsyncMock(return_value=[invoice]),claim_invoice_email=AsyncMock(return_value=True),complete_invoice_email=AsyncMock(),add_event=AsyncMock(),commit=AsyncMock())
        pdf=AsyncMock()
        monkeypatch.setattr(use_cases.GetInvoicePdfUseCase,'execute',pdf)
        await use_cases.DeliverPendingInvoiceEmailsUseCase(repo,None,SimpleNamespace()).execute()
        pdf.assert_not_awaited()
        repo.complete_invoice_email.assert_awaited_once_with(invoice.id,sent=False)
    sender.assert_not_called()


@pytest.mark.asyncio
async def test_confirmed_refusal_is_persisted_and_not_marked_sent(monkeypatch):
    service,row,repo=fixture_service()
    repo.db=db_with_blocked()
    row.email_recipients=['bad@recipient.org']
    monkeypatch.setattr(email_delivery,'check_invoice_recipients',AsyncMock())
    monkeypatch.setattr(email_delivery,'download_pdf',AsyncMock(return_value=b'%PDF-1.7'))
    monkeypatch.setattr(email_delivery,'send_invoice_pdf',Mock(side_effect=validation.MailboxNotFound('bad@recipient.org')))
    assert await service.deliver_pending()==0
    assert repo.db.execute.await_args.args[1]=={'email':'bad@recipient.org'}
    repo.delivered.assert_not_awaited()
    assert repo.complete.await_args.args[1]=='failed'
