"""Tests de autorización y semántica de las rutas de cuentas bancarias."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import app
from app.middlewares.auth import TokenAuthMiddleware
from app.modules.auth.infrastructure.dependencies import get_current_user_permissions
from app.modules.transactions.adapters.dependencies.transaction_dependencies import (
    delete_bank_account_uc,
    get_bank_account_by_id_uc,
    list_bank_accounts_uc,
)
from app.modules.transactions.application.schemas import BankAccountReadDTO

OWNER_ID = UUID("11111111-1111-1111-1111-111111111111")
STAFF_ID = UUID("22222222-2222-2222-2222-222222222222")
ACCOUNT_ID = UUID("33333333-3333-3333-3333-333333333333")


def _account(user_id: UUID = OWNER_ID) -> BankAccountReadDTO:
    return BankAccountReadDTO(
        id=ACCOUNT_ID,
        user_id=user_id,
        bank_id=uuid4(),
        account_flow="destination",
        account_holder_type="naturalPerson",
        bank_country="pe",
        cci_number="01123200020106262661",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def auth_required():
    """Fuerza `AUTH_REQUIRED=True` para que los guards se evalúen."""
    settings = get_settings()
    previous = settings.AUTH_REQUIRED
    settings.AUTH_REQUIRED = True
    yield
    settings.AUTH_REQUIRED = previous


@pytest.fixture
def bank_account_client(auth_required, monkeypatch):
    """Cliente con las dependencias de cuentas bancarias mockeadas.

    El middleware de token se sustituye por una sesión falsa para que el request
    llegue al handler con `AUTH_REQUIRED=True`.

    Devuelve `(client, configure, mocks)`: `configure(caller_id, permissions)`
    fija quién llama y con qué permisos.
    """
    existing = _account()
    session = {"user_id": str(STAFF_ID), "role": "sales"}

    async def fake_verify(self, token: str):
        return dict(session)

    monkeypatch.setattr(TokenAuthMiddleware, "_verify_token_in_database", fake_verify)

    get_uc = AsyncMock()
    get_uc.execute = AsyncMock(return_value=existing)
    delete_uc = AsyncMock()
    delete_uc.execute = AsyncMock(return_value=True)
    list_uc = AsyncMock()
    list_uc.execute = AsyncMock(return_value=[existing])

    app.dependency_overrides[get_bank_account_by_id_uc] = lambda: get_uc
    app.dependency_overrides[delete_bank_account_uc] = lambda: delete_uc
    app.dependency_overrides[list_bank_accounts_uc] = lambda: list_uc

    def configure(caller_id: UUID, permissions: list[str]) -> None:
        session["user_id"] = str(caller_id)
        app.dependency_overrides[get_current_user_permissions] = lambda: permissions

    configure(STAFF_ID, [])
    client = TestClient(app, headers={"Authorization": "Bearer test-token"})
    yield client, configure, {"get": get_uc, "delete": delete_uc, "list": list_uc}

    for dependency in (
        get_bank_account_by_id_uc,
        delete_bank_account_uc,
        list_bank_accounts_uc,
        get_current_user_permissions,
    ):
        app.dependency_overrides.pop(dependency, None)


def test_delete_without_permission_is_forbidden(bank_account_client):
    """Un usuario ajeno sin `bank_accounts.delete` no puede borrar la cuenta."""
    client, configure, mocks = bank_account_client
    configure(STAFF_ID, ["bank_accounts.view"])

    response = client.delete(f"/transactions/bank-accounts/{ACCOUNT_ID}")

    assert response.status_code == 403
    assert "bank_accounts.delete" in response.json()["detail"]
    mocks["delete"].execute.assert_not_awaited()


def test_delete_with_permission_succeeds(bank_account_client):
    client, configure, mocks = bank_account_client
    configure(STAFF_ID, ["bank_accounts.delete"])

    response = client.delete(f"/transactions/bank-accounts/{ACCOUNT_ID}")

    assert response.status_code == 204
    mocks["delete"].execute.assert_awaited_once_with(ACCOUNT_ID)


def test_owner_can_delete_own_account_without_permission(bank_account_client):
    """El cliente dueño administra su cuenta sin permisos de backoffice."""
    client, configure, mocks = bank_account_client
    configure(OWNER_ID, [])

    response = client.delete(f"/transactions/bank-accounts/{ACCOUNT_ID}")

    assert response.status_code == 204
    mocks["delete"].execute.assert_awaited_once_with(ACCOUNT_ID)


def test_delete_missing_account_returns_404(bank_account_client):
    client, configure, mocks = bank_account_client
    configure(STAFF_ID, ["bank_accounts.delete"])
    mocks["get"].execute = AsyncMock(return_value=None)

    response = client.delete(f"/transactions/bank-accounts/{uuid4()}")

    assert response.status_code == 404
    mocks["delete"].execute.assert_not_awaited()


def test_delete_returns_404_when_nothing_was_deleted(bank_account_client):
    """Si el soft-delete no encontró la fila, la respuesta no puede ser 204."""
    client, configure, mocks = bank_account_client
    configure(STAFF_ID, ["bank_accounts.delete"])
    mocks["delete"].execute = AsyncMock(return_value=False)

    response = client.delete(f"/transactions/bank-accounts/{ACCOUNT_ID}")

    assert response.status_code == 404


def test_get_by_id_without_permission_is_forbidden(bank_account_client):
    client, configure, _ = bank_account_client
    configure(STAFF_ID, [])

    response = client.get(f"/transactions/bank-accounts/{ACCOUNT_ID}")

    assert response.status_code == 403


def test_get_by_id_allows_owner(bank_account_client):
    client, configure, _ = bank_account_client
    configure(OWNER_ID, [])

    response = client.get(f"/transactions/bank-accounts/{ACCOUNT_ID}")

    assert response.status_code == 200
    assert response.json()["cci_number"] == "01123200020106262661"


def test_list_without_permission_is_scoped_to_caller(bank_account_client):
    """Sin `bank_accounts.view` el listado se limita a las cuentas propias."""
    client, configure, mocks = bank_account_client
    configure(OWNER_ID, [])

    response = client.get("/transactions/bank-accounts/")

    assert response.status_code == 200
    mocks["list"].execute.assert_awaited_once_with(user_id=OWNER_ID)


def test_list_of_another_user_without_permission_is_forbidden(bank_account_client):
    client, configure, mocks = bank_account_client
    configure(OWNER_ID, [])

    response = client.get(f"/transactions/bank-accounts/?user_id={STAFF_ID}")

    assert response.status_code == 403
    mocks["list"].execute.assert_not_awaited()


def test_list_with_permission_honours_filter(bank_account_client):
    client, configure, mocks = bank_account_client
    configure(STAFF_ID, ["bank_accounts.view"])

    response = client.get(f"/transactions/bank-accounts/?user_id={OWNER_ID}")

    assert response.status_code == 200
    mocks["list"].execute.assert_awaited_once_with(user_id=OWNER_ID)
