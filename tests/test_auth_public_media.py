"""Rutas de media públicas sin token."""
from app.middlewares.auth import TokenAuthMiddleware


def test_media_paths_do_not_require_auth():
    middleware = TokenAuthMiddleware(app=None)

    assert middleware._is_public_path("/media/home_banner/banner_es_ed4eb663.webp")
    assert middleware._is_public_path("/media/home_popup/popup_pr_abc123.webp")
    assert middleware._is_public_path("/media/profile_images/profile_abc123.webp")
    assert middleware._is_public_path("/media/profile_abc123.jpg")
    assert middleware._is_public_path("/media/transaction_vouchers/send_abc123.pdf")
