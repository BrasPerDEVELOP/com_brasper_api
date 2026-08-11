"""Regresiones de autorización por recurso y separación WWW/backoffice."""
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.core.settings import get_settings
from app.middlewares.auth import _EXACT_PUBLIC_ROUTES
from app.middlewares.auth import current_user_var
from app.modules.auth.domain.permissions import default_permissions_for_role
from app.modules.transactions.adapters.router.transaction_routes import (
    _ensure_transaction_owner_or_permission,
    _scope_transaction_user,
)


def test_www_public_allowlist_is_exact_and_automatic_coupon_only():
    expected_www_reads = {
        ("GET", "/blog"),
        ("GET", "/home-banner/home-image"),
        ("GET", "/home-banner/home-popup"),
        ("GET", "/coin/currencies"),
        ("GET", "/coin/tax-rate"),
        ("GET", "/coin/commission"),
        ("GET", "/transactions/coupons/automatic"),
    }
    assert expected_www_reads.issubset(_EXACT_PUBLIC_ROUTES)
    assert ("GET", "/transactions/coupons") not in _EXACT_PUBLIC_ROUTES
    assert ("GET", "/brasper/contact-form") not in _EXACT_PUBLIC_ROUTES
    assert ("GET", "/transactions") not in _EXACT_PUBLIC_ROUTES
    assert ("GET", "/user") not in _EXACT_PUBLIC_ROUTES


def test_client_default_permissions_exclude_backoffice_sensitive_modules():
    client_permissions = set(default_permissions_for_role("client"))
    admin_permissions = set(default_permissions_for_role("admin"))

    for permission in (
        "audit.view",
        "contact_forms.view",
        "company_bank_accounts.update",
        "integrations.view",
        "transactions.view",
    ):
        assert permission not in client_permissions
        assert permission in admin_permissions


def test_transaction_reads_are_scoped_to_the_authenticated_client():
    settings = get_settings()
    previous = settings.AUTH_REQUIRED
    settings.AUTH_REQUIRED = True
    owner_id = uuid4()
    other_id = uuid4()
    try:
        assert _scope_transaction_user(None, {"user_id": str(owner_id)}, []) == owner_id
        assert _scope_transaction_user(owner_id, {"user_id": str(owner_id)}, []) == owner_id
        with pytest.raises(HTTPException) as exc:
            _scope_transaction_user(other_id, {"user_id": str(owner_id)}, [])
        assert exc.value.status_code == 403

        assert _scope_transaction_user(other_id, {"user_id": str(owner_id)}, ["transactions.view"]) == other_id
    finally:
        settings.AUTH_REQUIRED = previous


def test_transaction_create_allows_owner_or_privileged_actor_only():
    settings = get_settings()
    previous = settings.AUTH_REQUIRED
    settings.AUTH_REQUIRED = True
    owner_id = uuid4()
    other_id = uuid4()
    try:
        _ensure_transaction_owner_or_permission(
            owner_id, {"user_id": str(owner_id)}, [], "transactions.create"
        )
        _ensure_transaction_owner_or_permission(
            other_id,
            {"user_id": str(owner_id)},
            ["transactions.create"],
            "transactions.create",
        )
        with pytest.raises(HTTPException) as exc:
            _ensure_transaction_owner_or_permission(
                other_id, {"user_id": str(owner_id)}, [], "transactions.create"
            )
        assert exc.value.status_code == 403
    finally:
        settings.AUTH_REQUIRED = previous


@pytest.mark.asyncio
async def test_private_voucher_allows_transaction_owner(monkeypatch):
    from app.main import _authorize_private_media

    settings = get_settings()
    previous = settings.AUTH_REQUIRED
    settings.AUTH_REQUIRED = True
    owner_id = uuid4()
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = owner_id
    db.execute = AsyncMock(return_value=result)

    class FakeSessionContext:
        async def __aenter__(self):
            return db

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr("app.db.base.AsyncSessionLocal", lambda: FakeSessionContext())
    token = current_user_var.set({"user_id": str(owner_id), "role": "client"})
    try:
        await _authorize_private_media("transaction_vouchers/send_private.pdf")
        db.execute.assert_awaited_once()
    finally:
        current_user_var.reset(token)
        settings.AUTH_REQUIRED = previous
