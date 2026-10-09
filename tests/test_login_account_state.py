"""El login no emite sesión para cuentas deshabilitadas/eliminadas ni filtra errores internos."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.auth.application.use_cases.auth_use_cases import LoginUseCase


def _use_case(user):
    uow = MagicMock()
    uow.auth_repository.get_by_username = AsyncMock(return_value=SimpleNamespace(id=uuid4(), username="svc", password="h"))
    uow.auth_repository.update_token = AsyncMock()
    uow.user_repository.get_by_auth_id = AsyncMock(return_value=user)
    uow.commit = AsyncMock()
    security = MagicMock()
    security.verify_password.return_value = True
    security.generate_opaque_token.return_value = "tok"
    return LoginUseCase(uow, security), uow


@pytest.mark.parametrize("state", [{"enable": False, "deleted": False}, {"enable": True, "deleted": True}])
async def test_disabled_or_deleted_account_gets_no_session(state):
    use_case, uow = _use_case(SimpleNamespace(id=uuid4(), **state))
    with pytest.raises(ValueError, match="Invalid username or password"):
        await use_case.execute(SimpleNamespace(username="svc", password="p"), "127.0.0.1")
    uow.auth_repository.update_token.assert_not_awaited()


def test_login_401_never_echoes_internal_validation_errors():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.core.container import get_login_uc
    from app.db.base import get_db
    from app.modules.auth.adapters.router.auth_routes import router

    app = FastAPI()
    db = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    app.dependency_overrides[get_db] = lambda: db
    failing = AsyncMock()
    failing.execute.side_effect = ValueError("1 validation error for UserInfoDTO email value is not a valid email")
    app.dependency_overrides[get_login_uc] = lambda: failing
    app.include_router(router)
    res = TestClient(app).post("/auth/login", json={"username": "user", "password": "pass"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid username or password"
