"""Regresión del transporte autenticado para comprobantes en ``<img src>``."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.middlewares.auth import TokenAuthMiddleware, get_current_user
from app.modules.auth.infrastructure.cookies import MEDIA_COOKIE_NAME, MEDIA_COOKIE_PATH


def _media_test_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(TokenAuthMiddleware)

    @app.get("/media/transaction_vouchers/{filename}")
    async def private_media(filename: str):
        return {"filename": filename, "user": get_current_user()}

    @app.get("/private")
    async def private_route():
        return {"ok": True}

    return app


def test_cookie_de_media_atraviesa_middleware_y_autentica(monkeypatch):
    async def authenticate(_self, token: str):
        assert token == "access-token"
        return {"user_id": "user-1", "session_id": "session-1"}

    monkeypatch.setattr(TokenAuthMiddleware, "_authenticate_token", authenticate)
    settings = get_settings()
    previous = settings.AUTH_REQUIRED
    settings.AUTH_REQUIRED = True
    try:
        client = TestClient(_media_test_app())
        client.cookies.set(MEDIA_COOKIE_NAME, "access-token", path=MEDIA_COOKIE_PATH)
        response = client.get("/media/transaction_vouchers/send_test.png")
    finally:
        settings.AUTH_REQUIRED = previous

    assert response.status_code == 200
    assert response.json()["user"]["user_id"] == "user-1"


def test_comprobante_sin_cookie_sigue_protegido():
    settings = get_settings()
    previous = settings.AUTH_REQUIRED
    settings.AUTH_REQUIRED = True
    try:
        response = TestClient(_media_test_app()).get(
            "/media/transaction_vouchers/send_test.png"
        )
    finally:
        settings.AUTH_REQUIRED = previous

    assert response.status_code == 401
    assert response.json() == {"detail": "Autenticación requerida"}


def test_cookie_de_media_no_autentica_otras_rutas(monkeypatch):
    async def must_not_authenticate(_self, _token: str):
        raise AssertionError("la cookie de media escapó de /media/transaction_vouchers")

    monkeypatch.setattr(TokenAuthMiddleware, "_authenticate_token", must_not_authenticate)
    settings = get_settings()
    previous = settings.AUTH_REQUIRED
    settings.AUTH_REQUIRED = True
    try:
        client = TestClient(_media_test_app())
        client.cookies.set(MEDIA_COOKIE_NAME, "access-token", path="/")
        response = client.get("/private")
    finally:
        settings.AUTH_REQUIRED = previous

    assert response.status_code == 401


def test_cookie_queda_confinada_a_media():
    assert MEDIA_COOKIE_PATH == "/media"
