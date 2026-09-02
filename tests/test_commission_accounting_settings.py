"""Tests de GET/POST /coin/commission-accounting/settings/."""
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import app
from app.middlewares.auth import TokenAuthMiddleware
from app.modules.auth.infrastructure.dependencies import get_current_user_permissions
from app.db.base import get_db
from app.modules.coin.adapters.dependencies.coin_dependencies import (
    get_commission_accounting_settings_uc,
    upsert_commission_accounting_settings_uc,
)
from app.modules.coin.application.schemas import CommissionAccountingSettingsReadDTO

STAFF_ID = UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def auth_required():
    settings = get_settings()
    previous = settings.AUTH_REQUIRED
    settings.AUTH_REQUIRED = True
    yield
    settings.AUTH_REQUIRED = previous


@pytest.fixture
def settings_client(auth_required, monkeypatch):
    session = {"user_id": str(STAFF_ID), "role": "accounting"}

    async def fake_verify(self, token: str):
        return dict(session)

    monkeypatch.setattr(TokenAuthMiddleware, "_authenticate_token", fake_verify)

    get_uc = AsyncMock()
    get_uc.execute = AsyncMock(
        return_value=CommissionAccountingSettingsReadDTO(
            amount_threshold=100, fixed_commission=3
        )
    )
    upsert_uc = AsyncMock()
    upsert_uc.execute = AsyncMock(
        return_value=CommissionAccountingSettingsReadDTO(
            amount_threshold=120, fixed_commission=5
        )
    )

    db_mock = MagicMock()
    db_mock.flush = AsyncMock()
    db_mock.commit = AsyncMock()
    app.dependency_overrides[get_db] = lambda: db_mock
    app.dependency_overrides[get_commission_accounting_settings_uc] = lambda: get_uc
    app.dependency_overrides[upsert_commission_accounting_settings_uc] = lambda: upsert_uc

    def configure(permissions: list[str]) -> None:
        app.dependency_overrides[get_current_user_permissions] = lambda: permissions

    configure([])
    client = TestClient(app, headers={"Authorization": "Bearer test-token"})
    yield client, configure, {"get": get_uc, "upsert": upsert_uc}

    for dependency in (
        get_db,
        get_commission_accounting_settings_uc,
        upsert_commission_accounting_settings_uc,
        get_current_user_permissions,
    ):
        app.dependency_overrides.pop(dependency, None)


def test_get_settings_without_permission_is_forbidden(settings_client):
    client, configure, mocks = settings_client
    configure(["commissions.update"])

    response = client.get("/coin/commission-accounting/settings/")

    assert response.status_code == 403
    mocks["get"].execute.assert_not_awaited()


def test_get_settings_ok(settings_client):
    client, configure, mocks = settings_client
    configure(["commissions.view"])

    response = client.get("/coin/commission-accounting/settings/")

    assert response.status_code == 200
    assert response.json() == {"amount_threshold": 100, "fixed_commission": 3}
    mocks["get"].execute.assert_awaited_once()


def test_post_settings_without_permission_is_forbidden(settings_client):
    client, configure, mocks = settings_client
    configure(["commissions.view"])

    response = client.post(
        "/coin/commission-accounting/settings/",
        json={"amount_threshold": 120, "fixed_commission": 5},
    )

    assert response.status_code == 403
    mocks["upsert"].execute.assert_not_awaited()


def test_post_settings_ok(settings_client):
    client, configure, mocks = settings_client
    configure(["commissions.update"])

    response = client.post(
        "/coin/commission-accounting/settings/",
        json={"amount_threshold": 120, "fixed_commission": 5},
    )

    assert response.status_code == 200
    assert response.json() == {"amount_threshold": 120, "fixed_commission": 5}
    mocks["upsert"].execute.assert_awaited_once()


def test_post_settings_validation_rejects_non_positive_threshold(settings_client):
    client, configure, mocks = settings_client
    configure(["commissions.update"])

    response = client.post(
        "/coin/commission-accounting/settings/",
        json={"amount_threshold": 0, "fixed_commission": 5},
    )

    assert response.status_code == 422
    mocks["upsert"].execute.assert_not_awaited()


def test_settings_path_is_not_treated_as_uuid(settings_client):
    """Regresión del 422: /settings no debe caer en /{commission_accounting_id}."""
    client, configure, mocks = settings_client
    configure(["commissions.view"])

    response = client.get("/coin/commission-accounting/settings")

    assert response.status_code == 200
    assert "amount_threshold" in response.json()
