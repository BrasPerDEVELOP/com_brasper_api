from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from fastapi import HTTPException

from app.modules.users.application.schemas.user_schema import UserCreateCmd, UserUpdateCmd, UserReadDTO
from app.modules.users.application.use_cases.user_use_cases import CreateUserUseCase, UpdateUserUseCase
from app.modules.billing.application import use_cases as billing
from app.modules.billing.application.schemas import SendInvoiceEmailCmd
from test_user_phone_area import user_record, form_cmd


def test_multipart_emails_normalize_primary_dedupe_and_clear():
    cmd = form_cmd(UserCreateCmd, email='legacy@example.com',
                   emails='[" principal@example.com ", "otro@example.com", "PRINCIPAL@example.com"]')
    assert cmd.emails == ['principal@example.com', 'otro@example.com']
    assert cmd.email == cmd.emails[0]
    clear = form_cmd(UserUpdateCmd, id=str(uuid4()), emails='[]')
    assert clear.emails == [] and clear.email is None
    omitted = form_cmd(UserUpdateCmd, id=str(uuid4()), names='Nuevo')
    assert omitted.emails is None and 'email' not in omitted.model_fields_set
    for raw in ('{}', '["invalido"]', 'broken'):
        with pytest.raises(HTTPException):
            form_cmd(UserCreateCmd, emails=raw)


@pytest.mark.parametrize('values', [['bad'], ['a@example.com'] * 21, [''], [42]])
def test_invalid_contact_lists_rejected(values):
    with pytest.raises(ValidationError):
        UserCreateCmd(emails=values)
    with pytest.raises(ValidationError):
        SendInvoiceEmailCmd(recipients=values)


@pytest.mark.asyncio
async def test_create_update_preserve_contacts_and_legacy_primary():
    user = user_record(email='principal@example.com', emails=['principal@example.com', 'other@example.com'])
    repo = SimpleNamespace(get=AsyncMock(return_value=user), update=AsyncMock(side_effect=lambda u: u),
                           add=AsyncMock(return_value=user))
    uow = SimpleNamespace(user_repository=repo, commit=AsyncMock(), rollback=AsyncMock())
    auth = SimpleNamespace(execute=AsyncMock())
    result = await CreateUserUseCase(uow, auth).execute(
        UserCreateCmd(emails=user.emails, role='client'), None)
    assert repo.add.await_args.args[0].emails == user.emails
    assert result.emails == user.emails
    auth.execute.assert_not_awaited()
    uc = UpdateUserUseCase(uow)
    await uc.execute(UserUpdateCmd(id=user.id, names='Nuevo'))
    assert user.emails == ['principal@example.com', 'other@example.com']
    await uc.execute(UserUpdateCmd(id=user.id, email='new@example.com'))
    assert user.emails == ['new@example.com', 'other@example.com']
    await uc.execute(UserUpdateCmd(id=user.id, emails=['other@example.com', 'new@example.com']))
    assert user.email == 'other@example.com'
    await uc.execute(UserUpdateCmd(id=user.id, emails=[]))
    assert user.emails == [] and user.email is None
    legacy = user_record(email='legacy@example.com')
    assert UserReadDTO.model_validate(legacy).emails == ['legacy@example.com']


def smtp_settings():
    return SimpleNamespace(BILLING_ENABLED=True, APISUNAT_ENVIRONMENT='production',
        SMTP_HOST='smtp.example.com', SMTP_USERNAME='test', SMTP_PASSWORD='test',
        SMTP_FROM_EMAIL='sender@example.com', SMTP_USE_TLS=True,
        billing_issuer=lambda ruc: None)


@pytest.mark.asyncio
async def test_queue_multiple_contacts_and_extras_without_changing_customer(monkeypatch):
    invoice = SimpleNamespace(id=uuid4(), transaction_id=uuid4(), status='accepted',
        environment='production', customer_email='original@example.com', email_delivered_to=['sent@example.com'])
    repo = SimpleNamespace(get_invoice=AsyncMock(return_value=invoice),
        queue_invoice_email=AsyncMock(return_value=True), commit=AsyncMock(), refresh=AsyncMock(), add_event=AsyncMock(),
        get_transaction_for_billing=AsyncMock(return_value=SimpleNamespace(user=SimpleNamespace(
            email='main@example.com', emails=['main@example.com', 'second@example.com']))))
    monkeypatch.setattr(billing.InvoiceDTO, 'from_entity', lambda entity: entity)
    uc = billing.RequestInvoiceEmailUseCase(repo, smtp_settings())
    await uc.execute(invoice.id, SendInvoiceEmailCmd())
    repo.queue_invoice_email.assert_awaited_with(invoice.id, ['main@example.com', 'second@example.com'])
    await uc.execute(invoice.id, SendInvoiceEmailCmd(recipients=['SENT@example.com', 'new@example.com', 'NEW@example.com']))
    repo.queue_invoice_email.assert_awaited_with(invoice.id, ['new@example.com'])
    assert invoice.customer_email == 'original@example.com'
    with pytest.raises(ValueError, match='ya fue enviado'):
        await uc.execute(invoice.id, SendInvoiceEmailCmd(recipients=['sent@example.com']))
    repo.queue_invoice_email.return_value = False
    with pytest.raises(ValueError, match='en curso'):
        await uc.execute(invoice.id, SendInvoiceEmailCmd(recipients=['extra@example.com']))


@pytest.mark.asyncio
async def test_retry_only_unsent_recipients_after_partial_smtp_failure(monkeypatch):
    invoice = SimpleNamespace(id=uuid4(), issuer_ruc='20611936428', full_number='BB02-00000001',
        email_recipients=['first@example.com', 'second@example.com'], email_delivered_to=[])
    async def record(invoice_id, recipient):
        invoice.email_delivered_to.append(recipient)
    repo = SimpleNamespace(list_pending_emails=AsyncMock(return_value=[invoice]),
        claim_invoice_email=AsyncMock(return_value=True), record_email_delivery=AsyncMock(side_effect=record),
        complete_invoice_email=AsyncMock(), add_event=AsyncMock(), commit=AsyncMock())
    monkeypatch.setattr(billing.GetInvoicePdfUseCase, 'execute', AsyncMock(return_value=(b'%PDF-test', 'test.pdf')))
    attempts = []
    def send(*args, **kwargs):
        attempts.append(kwargs['recipient'])
        if len(attempts) == 2:
            raise RuntimeError('SMTP unavailable')
    monkeypatch.setattr(billing, 'send_invoice_pdf', send)
    worker = billing.DeliverPendingInvoiceEmailsUseCase(repo, None, smtp_settings())
    assert await worker.execute() == 0
    assert invoice.email_delivered_to == ['first@example.com']
    repo.complete_invoice_email.assert_awaited_with(invoice.id, sent=False)
    assert await worker.execute() == 1
    assert attempts == ['first@example.com', 'second@example.com', 'second@example.com']
    repo.complete_invoice_email.assert_awaited_with(invoice.id, sent=True)
