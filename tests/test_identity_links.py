from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.brasper.application.identity_links import (
    ChannelSubject, IdentityLinks, RedeemLink, TooMany, Unavailable, digest,
)


def service():
    session = MagicMock()
    session.execute = AsyncMock()
    session.scalar = AsyncMock(return_value=0)
    session.commit = AsyncMock()
    links = IdentityLinks(session)
    links._user = AsyncMock(return_value=object())
    return links, session


async def test_issue_stores_only_hashes_and_binds_authenticated_owner():
    links, session = service()
    owner = uuid4()
    result = await links.issue(owner, ChannelSubject(channel="telegram", subject="tg:123"))
    row = session.add.call_args.args[0]
    assert row.user_id == owner and row.channel == "telegram"
    assert row.token_hash == digest(result["link_token"])
    assert row.subject_hash == digest("tg:123")
    assert result["link_token"] not in repr(row.__dict__)
    assert len(result["link_token"]) == 43


async def test_issue_rejects_inactive_user_and_limits_pending_tokens():
    links, session = service()
    links._user.return_value = None
    with pytest.raises(Unavailable):
        await links.issue(uuid4(), ChannelSubject(channel="telegram", subject="tg:123"))
    session.add.assert_not_called()
    links._user.return_value = object()
    session.scalar.return_value = 3
    with pytest.raises(TooMany):
        await links.issue(uuid4(), ChannelSubject(channel="telegram", subject="tg:123"))


async def test_redeem_lost_atomic_claim_cannot_return_grant():
    links, session = service()
    session.scalars = AsyncMock(return_value=SimpleNamespace(first=lambda: SimpleNamespace(id=uuid4(), user_id=uuid4())))
    session.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: None)
    with pytest.raises(Unavailable):
        await links.redeem(RedeemLink(channel="telegram", subject="tg:123", link_token="a" * 43))
    session.commit.assert_not_awaited()
    query = session.execute.call_args.args[0]
    assert "consumed_at IS NULL" in str(query) and "expires_at >" in str(query)


async def test_grant_checks_owner_channel_subject_expiry_and_active_account():
    links, session = service()
    owner = uuid4()
    session.scalars = AsyncMock(return_value=SimpleNamespace(first=lambda: object()))
    await links.authorize(owner, "secret", "telegram", "tg:123")
    query = session.scalars.call_args.args[0]
    params = query.compile().params.values()
    assert owner in params and digest("secret") in params and digest("tg:123") in params
    assert "grant_expires_at >" in str(query) and "consumed_at IS NOT NULL" in str(query)
    links._user.return_value = None
    with pytest.raises(Unavailable):
        await links.authorize(owner, "secret", "telegram", "tg:123")


@pytest.mark.parametrize("subject", ["tg:-123", "tg:0", "123", "tg:123/other"])
def test_telegram_link_requires_private_channel_subject(subject):
    with pytest.raises(ValidationError):
        ChannelSubject(channel="telegram", subject=subject)


def test_link_issuance_requires_session_even_when_general_auth_is_disabled():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.settings import get_settings
    settings = get_settings()
    previous = settings.BRASPER_IA_IDENTITY_LINK_ENABLED
    settings.BRASPER_IA_IDENTITY_LINK_ENABLED = True
    try:
        response = TestClient(app).post("/brasper/identity-links", json={"channel": "telegram", "subject": "tg:123"})
        assert response.status_code == 401
    finally:
        settings.BRASPER_IA_IDENTITY_LINK_ENABLED = previous


def test_link_feature_defaults_to_closed_and_redeem_requires_integration_secret():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.settings import get_settings
    settings = get_settings()
    previous = settings.BRASPER_IA_IDENTITY_LINK_ENABLED, settings.BRASPER_IA_SHARED_SECRET
    try:
        settings.BRASPER_IA_IDENTITY_LINK_ENABLED = False
        assert TestClient(app).post("/brasper/identity-links", json={"channel": "telegram", "subject": "tg:123"}).status_code == 503
        settings.BRASPER_IA_IDENTITY_LINK_ENABLED = True
        settings.BRASPER_IA_SHARED_SECRET = "test-secret"
        assert TestClient(app).post("/brasper/ai/identity-links/redeem", json={"channel": "telegram", "subject": "tg:123", "link_token": "a" * 43}).status_code == 401
    finally:
        settings.BRASPER_IA_IDENTITY_LINK_ENABLED, settings.BRASPER_IA_SHARED_SECRET = previous


async def test_revoke_all_retires_pending_codes_and_live_grants_of_owner_only():
    links, session = service()
    session.execute.return_value = SimpleNamespace(rowcount=2)
    owner = uuid4()
    assert await links.revoke_all(owner) == {"revoked": 2}
    query = session.execute.call_args.args[0]
    assert owner in query.compile().params.values()
    assert "consumed_at IS NULL" in str(query) and "grant_expires_at >" in str(query)
    session.commit.assert_awaited()


def test_revoke_requires_session():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.settings import get_settings
    settings = get_settings()
    previous = settings.BRASPER_IA_IDENTITY_LINK_ENABLED
    settings.BRASPER_IA_IDENTITY_LINK_ENABLED = True
    try:
        assert TestClient(app).delete("/brasper/identity-links").status_code == 401
    finally:
        settings.BRASPER_IA_IDENTITY_LINK_ENABLED = previous
