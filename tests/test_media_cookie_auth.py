"""
El navegador no manda `Authorization` al cargar un `<img>` ni al abrir el
comprobante en otra pestaña, así que /media respondía 401 para todos los
vouchers del panel. La cookie de `/media` transporta el mismo access token.
"""
import uuid

import pytest

from app.core.settings import get_settings
from app.main import _user_from_media_cookie
from app.modules.auth.adapters.router.auth_routes import MEDIA_COOKIE_NAME, MEDIA_COOKIE_PATH
from app.modules.auth.infrastructure.jwt_service import create_access_token


class _Request:
    def __init__(self, cookies):
        self.cookies = cookies


def _token(user_id: uuid.UUID) -> str:
    token, _ = create_access_token(
        user_id=user_id, session_id=uuid.uuid4(), client_app="backoffice"
    )
    return token


def test_identifica_al_usuario_desde_la_cookie():
    user_id = uuid.uuid4()
    resultado = _user_from_media_cookie(_Request({MEDIA_COOKIE_NAME: _token(user_id)}))
    assert resultado is not None
    assert resultado["user_id"] == str(user_id)
    assert resultado["client_app"] == "backoffice"


@pytest.mark.parametrize(
    "cookies",
    [
        {},
        {MEDIA_COOKIE_NAME: "no-es-un-jwt"},
        {MEDIA_COOKIE_NAME: ""},
        {"otra_cookie": "irrelevante"},
    ],
)
def test_sin_cookie_valida_no_identifica_a_nadie(cookies):
    assert _user_from_media_cookie(_Request(cookies)) is None


def test_una_cookie_firmada_con_otro_secreto_se_rechaza():
    import jwt

    settings = get_settings()
    ajeno = jwt.encode(
        {"sub": str(uuid.uuid4()), "sid": str(uuid.uuid4()), "jti": "x",
         "iss": settings.JWT_ISSUER, "aud": settings.JWT_AUDIENCE,
         "iat": 0, "nbf": 0, "exp": 9999999999, "client_app": "backoffice"},
        "secreto-que-no-es-el-nuestro",
        algorithm="HS256",
    )
    assert _user_from_media_cookie(_Request({MEDIA_COOKIE_NAME: ajeno})) is None


def test_la_cookie_queda_confinada_a_media():
    """Fuera de /media no debe viajar: no sustituye a la sesión."""
    assert MEDIA_COOKIE_PATH == "/media"
