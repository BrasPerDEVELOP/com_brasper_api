import smtplib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.modules.marketing import worker, routes, mail
from app.modules.marketing.schemas import DirectTestInput, TestInput as CampaignTestInput
from app.modules.billing.infrastructure.recipient_validation import MailboxNotFound, RecipientValidationError


def recipient(email='client@example.com'):
    return SimpleNamespace(email=email,status='pending',attempted_at=None,sent_at=None,error=None)


def database(*rows):
    result=MagicMock()
    campaign=SimpleNamespace(subject='Promo',body='Hello',template_key=None)
    result.first.side_effect=[(row,campaign) for row in rows]
    result.scalar_one.return_value=0
    return SimpleNamespace(execute=AsyncMock(return_value=result),get=AsyncMock(return_value=None),commit=AsyncMock())


@pytest.mark.asyncio
@pytest.mark.parametrize('error,status', [
    (RecipientValidationError('Dominio inválido'),'failed'),
    (RecipientValidationError('Consulta DNS temporalmente no disponible'),'failed'),
    (MailboxNotFound('client@example.com'),'failed'),
])
async def test_preflight_blocks_smtp_without_consuming_daily_allowance(monkeypatch,error,status):
    row=recipient()
    db=database(row)
    monkeypatch.setattr(worker,'check_invoice_recipients',AsyncMock(side_effect=error))
    sender=Mock()
    persist=AsyncMock()
    monkeypatch.setattr(worker,'send_email',sender)
    monkeypatch.setattr(worker,'record_invalid_mailbox',persist)
    assert await worker.deliver_one(db)
    assert row.status==status and row.error==str(error)
    assert row.attempted_at is None and row.sent_at is None
    sender.assert_not_called()
    persist.assert_not_awaited()


@pytest.mark.asyncio
async def test_bad_recipient_does_not_stop_valid_remaining_recipients(monkeypatch):
    bad,good=recipient('bad@example.com'),recipient('good@example.com')
    db=database(bad,good)
    check=AsyncMock(side_effect=[RecipientValidationError('Dominio inválido'),None])
    monkeypatch.setattr(worker,'check_invoice_recipients',check)
    sender=Mock()
    monkeypatch.setattr(worker,'send_email',sender)
    await worker.deliver_one(db)
    await worker.deliver_one(db)
    assert bad.status=='failed' and good.status=='sent'
    sender.assert_called_once_with(good.email,'Promo','Hello',False,None)
    assert good.sent_at is not None


@pytest.mark.asyncio
async def test_smtp_mailbox_rejection_is_shared_with_billing(monkeypatch):
    row=recipient()
    db=database(row)
    monkeypatch.setattr(worker,'check_invoice_recipients',AsyncMock())
    monkeypatch.setattr(worker,'send_email',Mock(side_effect=MailboxNotFound(row.email)))
    persist=AsyncMock()
    monkeypatch.setattr(worker,'record_invalid_mailbox',persist)
    await worker.deliver_one(db)
    persist.assert_awaited_once_with(db,row.email)
    assert row.status=='failed' and row.sent_at is None
    assert db.commit.await_count==2


@pytest.mark.asyncio
async def test_smtp_authentication_failure_never_blacklists_recipient(monkeypatch):
    row=recipient()
    db=database(row)
    monkeypatch.setattr(worker,'check_invoice_recipients',AsyncMock())
    monkeypatch.setattr(worker,'send_email',Mock(side_effect=smtplib.SMTPAuthenticationError(535,b'sensitive details')))
    persist=AsyncMock()
    monkeypatch.setattr(worker,'record_invalid_mailbox',persist)
    await worker.deliver_one(db)
    assert row.status=='failed' and 'sensitive' not in row.error
    persist.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('saved',[True,False])
async def test_both_test_endpoints_validate_before_sending(monkeypatch,saved):
    db=database()
    monkeypatch.setattr(routes,'check_config',lambda: None)
    monkeypatch.setattr(routes,'find_campaign',AsyncMock(return_value=SimpleNamespace(subject='Promo',body='Hello',template_key=None)))
    monkeypatch.setattr(routes,'check_invoice_recipients',AsyncMock(side_effect=RecipientValidationError('Dominio inválido')))
    sender=Mock()
    monkeypatch.setattr(routes,'send_email',sender)
    with pytest.raises(HTTPException) as error:
        if saved:
            await routes.test_send(uuid4(),CampaignTestInput(email='bad@example.com'),db)
        else:
            await routes.direct_test(DirectTestInput(email='bad@example.com',subject='Promo',body='Hello'),db)
    assert error.value.status_code==422 and error.value.detail=='Dominio inválido'
    sender.assert_not_called()


def test_sender_checks_domain_before_opening_smtp(monkeypatch):
    monkeypatch.setattr(mail,'validate_recipient_domain',Mock(side_effect=RecipientValidationError('Dominio inválido')))
    smtp=Mock()
    monkeypatch.setattr(mail.smtplib,'SMTP',smtp)
    with pytest.raises(RecipientValidationError):
        mail.send_email('bad@example.com','Promo','Hello')
    smtp.assert_not_called()


@pytest.mark.parametrize('refusal_kind',['exception','return'])
def test_sender_recognizes_confirmed_mailbox_rejection(monkeypatch,refusal_kind):
    monkeypatch.setattr(mail,'validate_recipient_domain',lambda email: email)
    monkeypatch.setattr(mail,'build_message',Mock(return_value=object()))
    monkeypatch.setattr(mail,'get_settings',lambda: SimpleNamespace(SMTP_HOST='smtp.example.com',SMTP_PORT=587,SMTP_USERNAME='test',SMTP_PASSWORD='test'))
    smtp=MagicMock()
    refused={'client@example.com':(550,b'5.1.1 No such user')}
    if refusal_kind=='exception':
        smtp.send_message.side_effect=smtplib.SMTPRecipientsRefused(refused)
    else:
        smtp.send_message.return_value=refused
    factory=MagicMock()
    factory.return_value.__enter__.return_value=smtp
    monkeypatch.setattr(mail.smtplib,'SMTP',factory)
    with pytest.raises(MailboxNotFound):
        mail.send_email('client@example.com','Promo','Hello')
