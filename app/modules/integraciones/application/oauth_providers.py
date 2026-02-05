# app/modules/integraciones/application/oauth_providers.py
"""URLs y lógica de intercambio de código por tokens y userinfo para Google y Facebook."""
import logging
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

# --- Google OAuth 2.0 ---
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_SCOPES = "openid email profile"


def google_authorize_url(
    client_id: str,
    redirect_uri: str,
    state: Optional[str] = None,
    scope: str = GOOGLE_SCOPES,
) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "prompt": "consent",
    }
    if state:
        params["state"] = state
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def google_exchange_code(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        return response.json()


async def google_userinfo(access_token: str) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()


# --- Facebook Login (OAuth 2.0) ---
FB_AUTH_URL = "https://www.facebook.com/v18.0/dialog/oauth"
FB_TOKEN_URL = "https://graph.facebook.com/v18.0/oauth/access_token"
FB_USERINFO_URL = "https://graph.facebook.com/me"
FB_SCOPES = "email,public_profile"


def facebook_authorize_url(
    client_id: str,
    redirect_uri: str,
    state: Optional[str] = None,
    scope: str = FB_SCOPES,
) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
    }
    if state:
        params["state"] = state
    return f"{FB_AUTH_URL}?{urlencode(params)}"


async def facebook_exchange_code(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            FB_TOKEN_URL,
            params={
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            },
        )
        response.raise_for_status()
        return response.json()


async def facebook_userinfo(access_token: str) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            FB_USERINFO_URL,
            params={
                "fields": "id,name,email,picture.type(large)",
                "access_token": access_token,
            },
        )
        response.raise_for_status()
        data = response.json()
        picture = data.get("picture", {}) or {}
        picture_data = picture.get("data", {}) or {}
        data["picture_url"] = picture_data.get("url")
        return data
