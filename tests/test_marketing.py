from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.modules.marketing.schemas import CampaignInput
from app.modules.marketing import mail, routes, worker


def campaign_payload(**overrides):
    return dict(name="Campaña", subject="Promoción", body="Hola", emails=["a@example.com"],
                consent_confirmed=True, **overrides)


def test_rejects_invalid_email_and_header_injection():
    data = campaign_payload()
    for key, value in [("emails", ["invalid"]), ("subject", "Hola\r\nBcc: victim@example.com"), ("body", "   ")]:
        with pytest.raises(ValidationError):
            CampaignInput(**{**data, key: value})


def test_signed_optout_is_scoped_and_tamperproof():
    from urllib.parse import parse_qs, urlparse
    token = parse_qs(urlparse(mail.unsubscribe_url("a@example.com")).query)["token"][0]
    assert mail.decode_unsubscribe(token) == "a@example.com"
    with pytest.raises(HTTPException):
        mail.decode_unsubscribe(token + "tampered")


async def test_no_creation_without_consent():
    db = MagicMock()
    with pytest.raises(HTTPException) as exc:
        await routes.create(CampaignInput(**{**campaign_payload(), "consent_confirmed": False}), db)
    assert exc.value.status_code == 422
    db.add.assert_not_called()


async def test_creation_deduplicates_addresses():
    db = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    result = MagicMock()
    result.all.return_value = [("pending", 1)]
    db.execute = AsyncMock(return_value=result)

    def add(item):
        item.id = uuid4()
        item.created_at = None
        item.status = "draft"
    db.add.side_effect = add
    await routes.create(CampaignInput(**{**campaign_payload(), "emails": ["A@example.com", "a@example.com"]}), db)
    assert len(db.add_all.call_args.args[0]) == 1


async def test_queue_cannot_resend_campaign(monkeypatch):
    monkeypatch.setattr(routes, "check_config", lambda: None)
    monkeypatch.setattr(routes, "get_settings", lambda: SimpleNamespace(MARKETING_ENABLED=True))
    monkeypatch.setattr(routes, "find_campaign", AsyncMock(return_value=SimpleNamespace(status="queued")))
    with pytest.raises(HTTPException) as exc:
        await routes.queue(uuid4(), MagicMock())
    assert exc.value.status_code == 409


async def test_worker_excludes_suppression_without_smtp(monkeypatch):
    recipient = SimpleNamespace(email="a@example.com", status="pending")
    db = MagicMock()
    result = MagicMock()
    result.first.return_value = (recipient, SimpleNamespace(subject="Hi", body="Hello"))
    db.execute = AsyncMock(return_value=result)
    db.get = AsyncMock(return_value=object())
    db.commit = AsyncMock()
    send = MagicMock()
    monkeypatch.setattr(worker, "send_email", send)
    await worker.deliver_one(db)
    assert recipient.status == "suppressed"
    send.assert_not_called()


@pytest.mark.parametrize("fails", [False, True])
async def test_worker_persists_claim_before_delivery_and_never_stores_smtp_error(monkeypatch, fails):
    recipient = SimpleNamespace(email="a@example.com", status="pending", error=None)
    db = MagicMock()
    result = MagicMock()
    result.first.return_value = (recipient, SimpleNamespace(subject="Hi", body="Hello"))
    result.scalar_one.return_value = 0
    db.execute = AsyncMock(return_value=result)
    db.get = AsyncMock(return_value=None)
    db.commit = AsyncMock()

    def send(*args):
        assert recipient.status == "processing"
        assert db.commit.await_count == 1
        if fails:
            raise RuntimeError("sensitive provider details")
    monkeypatch.setattr(worker, "send_email", send)
    await worker.deliver_one(db)
    assert recipient.status == ("failed" if fails else "sent")
    assert "sensitive" not in (recipient.error or "")
    assert db.commit.await_count == 2


def test_smtp_uses_tls_and_private_recipient(monkeypatch):
    settings = SimpleNamespace(SMTP_HOST="smtp.gmail.com", SMTP_PORT=587, SMTP_USERNAME="sender@example.com",
        SMTP_PASSWORD="secret", SMTP_FROM_EMAIL="sender@example.com", SMTP_USE_TLS=True,
        PUBLIC_URL="https://api.example.com", SECRET_KEY="test-key-which-is-long-enough-1234567890")
    monkeypatch.setattr(mail, "get_settings", lambda: settings)
    smtp = MagicMock()
    factory = MagicMock()
    factory.return_value.__enter__.return_value = smtp
    monkeypatch.setattr(mail.smtplib, "SMTP", factory)
    mail.send_email("recipient@example.com", "Promo", "<script>alert(1)</script>")
    smtp.starttls.assert_called_once()
    message = smtp.send_message.call_args.args[0]
    assert message["To"] == "recipient@example.com"
    assert message["Bcc"] is None
    assert "<script>" not in message.get_body(preferencelist=("html",)).get_content()
    assert "&lt;script&gt;" in message.get_body(preferencelist=("html",)).get_content()


def test_marketing_permissions_and_public_optout():
    from app.modules.auth.domain.permissions import ALL_PERMISSIONS, effective_permissions
    from app.middlewares.auth import TokenAuthMiddleware
    from starlette.requests import Request
    assert {"marketing.view", "marketing.create", "marketing.send"} <= set(ALL_PERMISSIONS)
    assert "marketing.send" in effective_permissions("marketing", None)
    middleware = TokenAuthMiddleware(None)
    for method in ("GET", "POST"):
        request = Request({"type": "http", "method": method, "path": "/marketing/unsubscribe", "headers": []})
        assert middleware._is_public_path(request)


async def test_direct_dispatch_queues_atomically_and_deduplicates(monkeypatch):
    from app.modules.marketing.schemas import DispatchInput
    monkeypatch.setattr(routes, 'check_config', lambda: None)
    monkeypatch.setattr(routes, 'get_settings', lambda: SimpleNamespace(MARKETING_ENABLED=True))
    dto = AsyncMock(return_value={'status': 'queued'})
    monkeypatch.setattr(routes, 'campaign_dto', dto)
    db = MagicMock()
    db.execute = AsyncMock()
    db.get = AsyncMock(return_value=None)
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    payload = DispatchInput(**{**campaign_payload(), 'emails':['a@example.com','A@example.com'], 'request_id': uuid4()})
    await routes.dispatch(payload, db)
    item = db.add.call_args.args[0]
    assert item.id == payload.request_id
    assert item.status == 'queued'
    assert len(db.add_all.call_args.args[0]) == 1
    db.commit.assert_awaited_once()


async def test_direct_dispatch_retry_returns_existing_without_requeue(monkeypatch):
    from app.modules.marketing.schemas import DispatchInput
    monkeypatch.setattr(routes, 'check_config', lambda: None)
    monkeypatch.setattr(routes, 'get_settings', lambda: SimpleNamespace(MARKETING_ENABLED=True))
    monkeypatch.setattr(routes, 'campaign_dto', AsyncMock(return_value={'status':'completed'}))
    payload = DispatchInput(**campaign_payload(), request_id=uuid4())
    existing = SimpleNamespace(id=payload.request_id, name=payload.name, subject=payload.subject, body=payload.body, template_key=None)
    result = MagicMock()
    result.scalars.return_value.all.return_value = ['a@example.com']
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    db.get = AsyncMock(return_value=existing)
    await routes.dispatch(payload, db)
    db.add.assert_not_called()
    payload.body = 'different'
    with pytest.raises(HTTPException) as exc:
        await routes.dispatch(payload, db)
    assert exc.value.status_code == 409


@pytest.mark.parametrize('enabled,consent,expected', [(False,True,503),(True,False,422)])
async def test_direct_dispatch_requires_enabled_and_consent(monkeypatch,enabled,consent,expected):
    from app.modules.marketing.schemas import DispatchInput
    monkeypatch.setattr(routes, 'check_config', lambda: None)
    monkeypatch.setattr(routes, 'get_settings', lambda: SimpleNamespace(MARKETING_ENABLED=enabled))
    db=MagicMock()
    with pytest.raises(HTTPException) as exc:
        await routes.dispatch(DispatchInput(**{**campaign_payload(),'consent_confirmed':consent},request_id=uuid4()),db)
    assert exc.value.status_code == expected
    db.add.assert_not_called()


async def test_unsaved_test_does_not_create_campaign_and_respects_optout(monkeypatch):
    from app.modules.marketing.schemas import DirectTestInput
    monkeypatch.setattr(routes, 'check_config', lambda: None)
    smtp=MagicMock()
    monkeypatch.setattr(routes, 'send_email', smtp)
    db=MagicMock()
    db.get=AsyncMock(return_value=object())
    payload=DirectTestInput(email='a@example.com',subject='Hello',body='Message')
    with pytest.raises(HTTPException) as exc:
        await routes.direct_test(payload,db)
    assert exc.value.status_code==409
    smtp.assert_not_called()
    db.get=AsyncMock(return_value=None)
    await routes.direct_test(payload,db)
    smtp.assert_called_once_with('a@example.com','Hello','Message',True,None)
    db.add.assert_not_called()


def test_unsaved_test_rejects_header_injection():
    from app.modules.marketing.schemas import DirectTestInput
    with pytest.raises(ValidationError):
        DirectTestInput(email='a@example.com',subject='hello\r\nBcc: x@example.com',body='Message')
