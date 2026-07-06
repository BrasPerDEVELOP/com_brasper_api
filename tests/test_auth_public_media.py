"""Rutas públicas sin token."""
from app.middlewares.auth import TokenAuthMiddleware


def test_media_paths_do_not_require_auth():
    middleware = TokenAuthMiddleware(app=None)

    assert middleware._is_public_path("/media/home_banner/banner_es_ed4eb663.webp")


def test_home_banner_list_is_public():
    middleware = TokenAuthMiddleware(app=None)

    assert middleware._is_public_path("/home-banner/home-image/")
    assert middleware._is_public_path("/home-banner/home-popup/")
