import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest
import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.db.base import get_db
from app.middlewares.auth import TokenAuthMiddleware
from app.modules.auth.domain.models import AuthSessionModel
from app.modules.auth.infrastructure.auth_session_repository import AuthSessionRepository
from app.modules.auth.infrastructure.jwt_service import (
    create_access_token,
    decode_access_token,
    generate_opaque_refresh_token,
    hash_refresh_token,
)
from app.modules.users.domain.models import User as UserModel


def _utc_now():
    return datetime.now(timezone.utc)


def _mock_db() -> MagicMock:
    db = MagicMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


# --- 1. Pruebas de repositorio de sesiones aisladas con Mocks / Fakes ---

@pytest.mark.asyncio
async def test_repository_create_session_no_internal_commit():
    db = _mock_db()
    repo = AuthSessionRepository(db)
    user_id = uuid.uuid4()

    session, raw_token = await repo.create_session(user_id=user_id, client_app="backoffice")

    assert session.user_id == user_id
    assert session.rotation_number == 1
    assert len(raw_token) >= 32
    db.add.assert_called_once()
    db.flush.assert_awaited_once()
    db.commit.assert_not_called()  # Debe diferir commit al llamador


@pytest.mark.asyncio
async def test_repository_rotate_refresh_token_for_update_and_success():
    db = _mock_db()
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    family_id = uuid.uuid4()
    raw_token, token_hash = generate_opaque_refresh_token()

    now = _utc_now()
    old_session = AuthSessionModel(
        id=session_id,
        user_id=user_id,
        refresh_token_hash=token_hash,
        family_id=family_id,
        rotation_number=1,
        client_app="backoffice",
        expires_at=now + timedelta(days=7),
        revoked_at=None,
    )
    user = UserModel(id=user_id, deleted=False, enable=True)

    result_mock = MagicMock()
    result_mock.first.return_value = (old_session, user)
    db.execute.return_value = result_mock

    repo = AuthSessionRepository(db)
    new_session, new_raw_token = await repo.rotate_refresh_token(raw_token)

    assert old_session.revoked_at is not None
    assert old_session.revoke_reason == "rotated"
    assert new_session.family_id == family_id
    assert new_session.parent_session_id == session_id
    assert new_session.rotation_number == 2
    db.commit.assert_not_called()  # Deja la transacción abierta al route para auditoría y commit único


@pytest.mark.asyncio
async def test_repository_rotate_reuse_detected_revokes_family():
    db = _mock_db()
    user_id = uuid.uuid4()
    family_id = uuid.uuid4()
    raw_token, token_hash = generate_opaque_refresh_token()

    now = _utc_now()
    revoked_session = AuthSessionModel(
        id=uuid.uuid4(),
        user_id=user_id,
        refresh_token_hash=token_hash,
        family_id=family_id,
        rotation_number=1,
        client_app="backoffice",
        expires_at=now + timedelta(days=7),
        revoked_at=now - timedelta(minutes=5),  # Ya revocada previamente
        revoke_reason="rotated",
    )
    user = UserModel(id=user_id, deleted=False, enable=True)

    result_mock = MagicMock()
    result_mock.first.return_value = (revoked_session, user)
    db.execute.return_value = result_mock

    repo = AuthSessionRepository(db)
    with pytest.raises(ValueError, match="Reutilización"):
        await repo.rotate_refresh_token(raw_token)

    assert revoked_session.reuse_detected_at is not None
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_repository_disabled_user_rejected():
    db = _mock_db()
    raw_token, _ = generate_opaque_refresh_token()

    result_mock = MagicMock()
    result_mock.first.return_value = None  # Filtro por enable=True y deleted=False no devuelve fila
    db.execute.return_value = result_mock

    repo = AuthSessionRepository(db)
    with pytest.raises(ValueError, match="inválido o usuario no activo"):
        await repo.rotate_refresh_token(raw_token)


# --- 2. Pruebas de Endpoints Auth (/login, /refresh, /logout, cookies y origin) ---

def test_login_commit_and_cookie_attributes(monkeypatch):
    app = FastAPI()
    from app.modules.auth.adapters.router.auth_routes import router

    db = _mock_db()
    app.dependency_overrides[get_db] = lambda: db

    # Mock LoginUseCase
    user_mock = MagicMock()
    user_mock.id = uuid.uuid4()
    user_mock.model_dump.return_value = {"id": str(user_mock.id), "email": "test@example.com"}

    result_mock = MagicMock()
    result_mock.user = user_mock

    use_case_mock = AsyncMock()
    use_case_mock.execute.return_value = result_mock

    from app.core.container import get_login_uc
    app.dependency_overrides[get_login_uc] = lambda: use_case_mock

    app.include_router(router)
    client = TestClient(app)

    res = client.post("/auth/login", json={"username": "user", "password": "pass"})
    assert res.status_code == 200
    db.commit.assert_awaited_once()  # Verifica commit de sesión antes de responder

    settings = get_settings()
    cookie_header = res.headers.get("set-cookie", "")
    assert settings.REFRESH_COOKIE_NAME in cookie_header
    assert "HttpOnly" in cookie_header
    assert "Path=/auth" in cookie_header
    assert f"SameSite={settings.REFRESH_COOKIE_SAMESITE.lower()}" in cookie_header


def test_legacy_login_returns_opaque_token_without_refresh_cookie():
    app = FastAPI()
    from app.core.container import get_login_uc
    from app.modules.auth.adapters.router.auth_routes import router

    db = _mock_db()
    app.dependency_overrides[get_db] = lambda: db
    user = MagicMock()
    user.id = uuid.uuid4()
    user.model_dump.return_value = {"id": str(user.id)}
    result = MagicMock(user=user, token="legacy-opaque-token")
    use_case = AsyncMock()
    use_case.execute.return_value = result
    app.dependency_overrides[get_login_uc] = lambda: use_case
    app.include_router(router)

    settings = get_settings()
    original_mode = settings.AUTH_MODE
    settings.AUTH_MODE = "legacy"
    try:
        response = TestClient(app).post(
            "/auth/login",
            json={"username": "user", "password": "pass"},
        )
    finally:
        settings.AUTH_MODE = original_mode

    assert response.status_code == 200
    assert response.json()["access_token"] == "legacy-opaque-token"
    assert settings.REFRESH_COOKIE_NAME not in response.headers.get("set-cookie", "")
    db.commit.assert_awaited_once()  # Token opaco y auditoría confirman juntos


@pytest.mark.parametrize("provider", ["facebook", "google"])
def test_social_login_issues_same_session_cookies_as_password_login(provider):
    """Quien entra por una red social necesita las mismas dos cookies que quien usa contraseña."""
    app = FastAPI()
    from app.modules.integraciones.adapters.dependencies.integration_dependencies import (
        get_oauth_callback_uc,
    )
    from app.modules.auth.adapters.router.auth_routes import router
    from app.modules.auth.infrastructure.cookies import MEDIA_COOKIE_NAME

    db = _mock_db()
    app.dependency_overrides[get_db] = lambda: db

    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "social@example.com"
    user.model_dump.return_value = {"id": str(user.id), "email": user.email}
    use_case = AsyncMock()
    use_case.execute.return_value = MagicMock(user=user, token="opaque-from-oauth")
    app.dependency_overrides[get_oauth_callback_uc] = lambda: use_case
    app.include_router(router)

    response = TestClient(app).post(f"/auth/{provider}", json={"code": "oauth-code"})

    assert response.status_code == 200
    settings = get_settings()
    cookies = response.headers.get_list("set-cookie")
    assert any(settings.REFRESH_COOKIE_NAME in cookie for cookie in cookies)
    assert any(MEDIA_COOKIE_NAME in cookie for cookie in cookies)
    # El access token es el JWT de la sesión nueva, no el token opaco del canje.
    assert response.json()["access_token"] != "opaque-from-oauth"
    db.commit.assert_awaited_once()


def test_refresh_rejects_body_and_requires_cookie():
    app = FastAPI()
    from app.modules.auth.adapters.router.auth_routes import router

    db = _mock_db()
    app.dependency_overrides[get_db] = lambda: db
    app.include_router(router)
    client = TestClient(app)

    # Intentar enviar por body debe ser rechazado si no hay cookie
    res = client.post("/auth/refresh", json={"refresh_token": "some-token"})
    assert res.status_code == 401
    assert "cookie" in res.json()["detail"].lower()


def test_refresh_rotates_cookie_and_loads_user_for_audit(monkeypatch):
    from app.modules.auth.adapters.router import auth_routes

    app = FastAPI()
    db = _mock_db()
    db.get = AsyncMock()
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    user = MagicMock(email="audit@example.com", username="audit", role="admin")
    db.get.return_value = user
    new_session = MagicMock(
        id=session_id,
        user_id=user_id,
        client_app="backoffice",
    )

    rotate_refresh_token = AsyncMock(return_value=(new_session, "new-refresh-token"))
    log_audit_event = AsyncMock()
    monkeypatch.setattr(
        auth_routes.AuthSessionRepository,
        "rotate_refresh_token",
        rotate_refresh_token,
    )
    monkeypatch.setattr(
        auth_routes.AuditRepository,
        "log_audit_event",
        log_audit_event,
    )

    app.dependency_overrides[get_db] = lambda: db
    app.include_router(auth_routes.router)
    settings = get_settings()
    client = TestClient(app)
    client.cookies.set(settings.REFRESH_COOKIE_NAME, "old-refresh-token", path="/auth")
    response = client.post("/auth/refresh")

    assert response.status_code == 200
    assert response.json()["access_token"]
    db.get.assert_awaited_once_with(UserModel, user_id)
    log_audit_event.assert_awaited_once()
    db.commit.assert_awaited_once()
    assert settings.REFRESH_COOKIE_NAME in response.headers.get("set-cookie", "")


def test_refresh_and_logout_reject_hostile_origin():
    app = FastAPI()
    from app.modules.auth.adapters.router.auth_routes import router

    db = _mock_db()
    app.dependency_overrides[get_db] = lambda: db
    app.include_router(router)
    client = TestClient(app)

    headers = {"Origin": "http://evil-attacker.com"}
    res_ref = client.post("/auth/refresh", headers=headers)
    assert res_ref.status_code == 403

    res_log = client.post("/auth/logout", headers=headers)
    assert res_log.status_code == 403


# --- 3. Pruebas de Middleware Auth y Modos (Sin reemplazar _authenticate_token) ---

def test_middleware_jwt_claim_sub_mismatch_rejected(monkeypatch):
    app = FastAPI()

    async def mock_get_active(session_id):
        # La sesión en BD tiene user_id_A
        s_model = MagicMock()
        s_model.id = session_id
        s_model.user_id = uuid.uuid4()
        s_model.client_app = "backoffice"

        u_model = MagicMock()
        u_model.id = s_model.user_id
        u_model.enable = True
        u_model.deleted = False
        u_model.names = "User A"
        return (s_model, u_model)

    monkeypatch.setattr(AuthSessionRepository, "get_active_session_with_user", lambda self, sid: mock_get_active(sid))

    app.add_middleware(TokenAuthMiddleware)

    @app.get("/test")
    def endpoint():
        return {"ok": True}

    client = TestClient(app)

    # JWT con sub = user_id_B (diferente a user_id_A de la sesión)
    different_user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    token, _ = create_access_token(user_id=different_user_id, session_id=session_id, client_app="backoffice")

    settings = get_settings()
    orig_req = settings.AUTH_REQUIRED
    settings.AUTH_REQUIRED = True

    try:
        res = client.get("/test", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401
    finally:
        settings.AUTH_REQUIRED = orig_req


def test_middleware_dual_mode_does_not_downgrade_3_segment_jwt(monkeypatch):
    app = FastAPI()
    settings = get_settings()

    orig_mode = settings.AUTH_MODE
    orig_req = settings.AUTH_REQUIRED
    settings.AUTH_MODE = "dual"
    settings.AUTH_REQUIRED = True

    called_opaque = False

    async def mock_opaque(self, token):
        nonlocal called_opaque
        called_opaque = True
        return {"user_id": "opaque-user"}

    monkeypatch.setattr(TokenAuthMiddleware, "_verify_opaque_token_in_database", mock_opaque)

    app.add_middleware(TokenAuthMiddleware)

    @app.get("/test")
    def endpoint():
        return {"ok": True}

    client = TestClient(app)

    # Un token con 3 segmentos pero firma inválida/falsa no debe llamar a _verify_opaque_token_in_database
    fake_jwt_token = "header.payload.signature"
    res = client.get("/test", headers={"Authorization": f"Bearer {fake_jwt_token}"})

    assert res.status_code == 401
    assert called_opaque is False  # Impide downgrade a token opaco

    settings.AUTH_MODE = orig_mode
    settings.AUTH_REQUIRED = orig_req


@pytest.mark.asyncio
async def test_authenticate_token_honours_legacy_dual_and_jwt_modes(monkeypatch):
    middleware = TokenAuthMiddleware(app=None)
    calls: list[tuple[str, str]] = []

    async def verify_jwt(_self, token):
        calls.append(("jwt", token))
        return {"kind": "jwt"}

    async def verify_opaque(_self, token):
        calls.append(("opaque", token))
        return {"kind": "opaque"}

    monkeypatch.setattr(TokenAuthMiddleware, "_verify_jwt", verify_jwt)
    monkeypatch.setattr(
        TokenAuthMiddleware,
        "_verify_opaque_token_in_database",
        verify_opaque,
    )
    settings = get_settings()
    original_mode = settings.AUTH_MODE
    try:
        settings.AUTH_MODE = "legacy"
        assert (await middleware._authenticate_token("opaque"))["kind"] == "opaque"
        settings.AUTH_MODE = "dual"
        assert (await middleware._authenticate_token("opaque"))["kind"] == "opaque"
        assert (await middleware._authenticate_token("a.b.c"))["kind"] == "jwt"
        settings.AUTH_MODE = "jwt"
        assert (await middleware._authenticate_token("anything"))["kind"] == "jwt"
    finally:
        settings.AUTH_MODE = original_mode

    assert calls == [
        ("opaque", "opaque"),
        ("opaque", "opaque"),
        ("jwt", "a.b.c"),
        ("jwt", "anything"),
    ]
