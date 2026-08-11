"""Valida el guardia de arranque que evita cookies de refresh inalcanzables."""
import pytest

from app.core.settings import Settings, _registrable_domain


def _settings(**overrides):
    base = dict(
        ENVIRONMENT="production",
        PUBLIC_URL="https://apibras.finzeler.com",
        JWT_SECRET_KEY="x" * 40,
        SECRET_KEY="y" * 40,
        AUTH_REQUIRED=True,
        REFRESH_COOKIE_SECURE=True,
        POSTGRES_DB="db",
        POSTGRES_USER="u",
        POSTGRES_PASSWORD="p",
        POSTGRES_HOST="h",
        POSTGRES_PORT=5432,
        R2_ENDPOINT_URL="https://r2.example.com",
        R2_ACCESS_KEY_ID="b",
        R2_SECRET_ACCESS_KEY="c",
        R2_BUCKET_NAME="d",
    )
    base.update(overrides)
    return base


@pytest.mark.parametrize(
    "host,expected",
    [
        ("apibras.finzeler.com", "finzeler.com"),
        ("bo.brasper.com.pe", "brasper.com.pe"),
        ("brasper.com", "brasper.com"),
        ("localhost", "localhost"),
    ],
)
def test_registrable_domain(host, expected):
    assert _registrable_domain(host) == expected


def test_same_registrable_domain_admite_samesite_lax():
    settings = Settings(
        **_settings(
            CORS_ALLOWED_ORIGINS=["https://bo.finzeler.com"],
            REFRESH_COOKIE_SAMESITE="lax",
        )
    )
    assert settings.REFRESH_COOKIE_SAMESITE == "lax"


def test_cross_site_con_samesite_lax_falla_al_arrancar():
    with pytest.raises(ValueError, match="cross-site"):
        Settings(
            **_settings(
                CORS_ALLOWED_ORIGINS=["https://backoffice.brasper.com"],
                REFRESH_COOKIE_SAMESITE="lax",
            )
        )


def test_cross_site_con_samesite_none_es_valido():
    settings = Settings(
        **_settings(
            CORS_ALLOWED_ORIGINS=["https://backoffice.brasper.com"],
            REFRESH_COOKIE_SAMESITE="none",
        )
    )
    assert settings.REFRESH_COOKIE_SAMESITE == "none"


def test_localhost_no_dispara_el_guardia():
    settings = Settings(
        **_settings(
            CORS_ALLOWED_ORIGINS=["http://localhost:5173"],
            REFRESH_COOKIE_SAMESITE="lax",
        )
    )
    assert settings.REFRESH_COOKIE_SAMESITE == "lax"
