# app/modules/auth/infrastructure/jwt_service.py
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Tuple
import jwt
from app.core.settings import get_settings


def create_access_token(
    user_id: str | uuid.UUID,
    session_id: str | uuid.UUID,
    client_app: str = "backoffice",
    expires_delta: timedelta | None = None,
) -> Tuple[str, str]:
    """
    Emite un Access Token JWT firmado con claims obligatorios:
    sub, sid, jti, iss, aud, iat, nbf, exp, client_app.
    Devuelve (token, jti).
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    jti = str(uuid.uuid4())

    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_ACCESS_TTL_MINUTES)

    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "sid": str(session_id),
        "jti": jti,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "client_app": client_app,
    }

    token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    return token, jti


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Valida y decodifica el Access Token JWT exigiendo algoritmo, issuer y audience explícitos.
    Lanza jwt.PyJWTError si es inválido o alterado.
    """
    settings = get_settings()

    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        issuer=settings.JWT_ISSUER,
        audience=settings.JWT_AUDIENCE,
        options={
            "require": ["sub", "sid", "jti", "iss", "aud", "iat", "nbf", "exp", "client_app"],
            "verify_signature": True,
            "verify_exp": True,
            "verify_nbf": True,
            "verify_iat": True,
            "verify_iss": True,
            "verify_aud": True,
        },
    )
    return payload


def generate_opaque_refresh_token() -> Tuple[str, str]:
    """
    Genera un refresh token opaco y aleatorio seguro y calcula su hash SHA-256.
    Devuelve (raw_token, hash_hex).
    """
    raw_token = secrets.token_urlsafe(48)
    token_hash = hash_refresh_token(raw_token)
    return raw_token, token_hash


def hash_refresh_token(token: str) -> str:
    """Calcula el hash SHA-256 de un refresh token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
