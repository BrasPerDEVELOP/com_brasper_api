# app/modules/integraciones/adapters/router/oauth_routes.py
"""Rutas para login OAuth con Google y Facebook."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from app.core.settings import get_settings
from app.modules.auth.application.schemas.auth_schema import TokenInfoDTO
from app.modules.integraciones.adapters.dependencies import (
    GetOAuthAuthorizeUrlUseCaseDep,
    OAuthCallbackUseCaseDep,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth", tags=["oauth"])


def _base_callback_url(provider: str) -> str:
    settings = get_settings()
    base = (settings.PUBLIC_URL or "").rstrip("/")
    return f"{base}/integraciones/oauth/{provider}/callback"


@router.get("/google", response_class=RedirectResponse)
async def oauth_google_authorize(
    use_case: GetOAuthAuthorizeUrlUseCaseDep,
    redirect_uri: Optional[str] = Query(None, description="URI de callback (opcional)"),
    state: Optional[str] = Query(None, description="State para CSRF (opcional)"),
):
    """Redirige al usuario a la pantalla de login de Google."""
    try:
        callback = redirect_uri or _base_callback_url("google")
        url = await use_case.execute(provider="google", redirect_uri=callback, state=state)
        return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)
    except ValueError as e:
        logger.warning(f"OAuth Google authorize error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/google/callback")
async def oauth_google_callback(
    use_case: OAuthCallbackUseCaseDep,
    code: str = Query(..., description="Código de autorización de Google"),
    state: Optional[str] = Query(None),
    redirect_uri: Optional[str] = Query(None),
    redirect: Optional[str] = Query(
        None,
        description="Si se envía, redirige al frontend con token en query (ej. URL del frontend)",
    ),
):
    """Recibe el callback de Google, intercambia código por token y devuelve sesión (token + user)."""
    try:
        callback = redirect_uri or _base_callback_url("google")
        result: TokenInfoDTO = await use_case.execute(
            provider="google", code=code, redirect_uri=callback
        )
        if redirect:
            # Redirigir al frontend con token en query (el frontend debe guardarlo y quitar de URL)
            sep = "&" if "?" in redirect else "?"
            return RedirectResponse(
                url=f"{redirect}{sep}access_token={result.token}&token_type=bearer",
                status_code=status.HTTP_302_FOUND,
            )
        return result
    except ValueError as e:
        logger.warning(f"OAuth Google callback error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/facebook", response_class=RedirectResponse)
async def oauth_facebook_authorize(
    use_case: GetOAuthAuthorizeUrlUseCaseDep,
    redirect_uri: Optional[str] = Query(None, description="URI de callback (opcional)"),
    state: Optional[str] = Query(None, description="State para CSRF (opcional)"),
):
    """Redirige al usuario a la pantalla de login de Facebook."""
    try:
        callback = redirect_uri or _base_callback_url("facebook")
        url = await use_case.execute(provider="facebook", redirect_uri=callback, state=state)
        return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)
    except ValueError as e:
        logger.warning(f"OAuth Facebook authorize error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/facebook/callback")
async def oauth_facebook_callback(
    use_case: OAuthCallbackUseCaseDep,
    code: str = Query(..., description="Código de autorización de Facebook"),
    state: Optional[str] = Query(None),
    redirect_uri: Optional[str] = Query(None),
    redirect: Optional[str] = Query(
        None,
        description="Si se envía, redirige al frontend con token en query",
    ),
):
    """Recibe el callback de Facebook, intercambia código por token y devuelve sesión (token + user)."""
    try:
        callback = redirect_uri or _base_callback_url("facebook")
        result: TokenInfoDTO = await use_case.execute(
            provider="facebook", code=code, redirect_uri=callback
        )
        if redirect:
            sep = "&" if "?" in redirect else "?"
            return RedirectResponse(
                url=f"{redirect}{sep}access_token={result.token}&token_type=bearer",
                status_code=status.HTTP_302_FOUND,
            )
        return result
    except ValueError as e:
        logger.warning(f"OAuth Facebook callback error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
