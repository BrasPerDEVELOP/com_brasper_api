import logging
import re
from typing import Optional
import uuid
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from contextvars import ContextVar
from datetime import datetime, timedelta

from app.core.settings import get_settings
from app.modules.auth.infrastructure.cookies import MEDIA_COOKIE_NAME
from app.modules.auth.infrastructure.jwt_service import decode_access_token

logger = logging.getLogger(__name__)

current_user_var = ContextVar("current_user", default=None)
current_token_var = ContextVar("current_token", default=None)


def get_current_user() -> Optional[dict]:
    return current_user_var.get()


def get_current_token() -> Optional[str]:
    return current_token_var.get()


# Patrones compilados y anclados para rutas públicas con parámetros o wildcard
_PUBLIC_MEDIA_PATTERN = re.compile(
    r"^/media/(?:profile_images|home_banner|home_popup)/[^/].*$",
    re.IGNORECASE,
)
_LEGACY_PROFILE_MEDIA_PATTERN = re.compile(
    r"^/media/profile_[a-zA-Z0-9\-]+\.(?:jpg|jpeg|png|webp|gif)/?$",
    re.IGNORECASE,
)
_PRIVATE_TRANSACTION_MEDIA_PATTERN = re.compile(
    r"^/media/transaction_vouchers/[^/]+/?$",
    re.IGNORECASE,
)
_BLOG_SLUG_PATTERN = re.compile(r"^/blog/slug/[^/]+/?$", re.IGNORECASE)
_HOME_BANNER_ID_PATTERN = re.compile(r"^/home-banner/home-image/[^/]+/?$", re.IGNORECASE)
_HOME_POPUP_ID_PATTERN = re.compile(r"^/home-banner/home-popup/[^/]+/?$", re.IGNORECASE)

# Lista de rutas públicas exactas sin barras finales (salvo '/')
_EXACT_PUBLIC_ROUTES = {
    ("GET", "/"),
    ("GET", "/health"),
    ("GET", "/blog"),
    ("GET", "/home-banner/home-image"),
    ("GET", "/home-banner/home-popup"),
    ("GET", "/coin/currencies"),
    ("GET", "/coin/tax-rate"),
    ("GET", "/coin/commission"),
    ("GET", "/transactions/coupons/automatic"),
    ("POST", "/auth/login"),
    ("POST", "/auth/refresh"),
    ("POST", "/auth/reset-password"),
    ("POST", "/auth/reset-password/confirm"),
    ("POST", "/user"),
    ("POST", "/brasper/contact-form"),
}

# Alias legacy exactos permitidos (variante con una sola barra final)
_LEGACY_ALIAS_PUBLIC_ROUTES = {
    (method, f"{path}/") for method, path in _EXACT_PUBLIC_ROUTES if path != "/"
}


class TokenAuthMiddleware(BaseHTTPMiddleware):
    """Middleware de autenticación con soporte para modos legacy, dual y jwt."""

    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        current_user_var.set(None)
        current_token_var.set(None)

        settings = get_settings()

        if not settings.AUTH_REQUIRED:
            token = self._extract_token(request)
            if token:
                user_data = await self._authenticate_token(token)
                if user_data:
                    current_user_var.set(user_data)
                    current_token_var.set(token)
            return await call_next(request)

        if self._is_public_path(request):
            # Las rutas públicas aceptan acceso anónimo, pero si el cliente envía
            # Bearer se autentica de forma oportunista. Esto permite que POST
            # /user distinga un registro público de una creación administrativa
            # sin abrir una vía para escoger roles privilegiados.
            token = self._extract_token(request)
            if token:
                user_data = await self._authenticate_token(token)
                if not user_data:
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Invalid or expired token"},
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                current_user_var.set(user_data)
                current_token_var.set(token)
            return await call_next(request)

        token = self._extract_token(request)
        if not token:
            logger.warning(f"No token provided for protected path: {request.url.path}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Autenticación requerida"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_data = await self._authenticate_token(token)

        if not user_data:
            logger.warning(f"Invalid or expired token for path: {request.url.path}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"},
                headers={"WWW-Authenticate": "Bearer"}
            )

        current_user_var.set(user_data)
        current_token_var.set(token)
        logger.debug(f"Token validated for user: {user_data.get('username')}")
        return await call_next(request)

    def _extract_token(self, request: Request) -> Optional[str]:
        """Extrae Bearer o, solo para comprobantes, la cookie confinada a /media."""
        authorization = request.headers.get("Authorization")
        if authorization:
            if authorization.startswith("Bearer "):
                return authorization[7:]
            return None

        if self._is_private_media_path(request):
            return request.cookies.get(MEDIA_COOKIE_NAME)

        return None

    def _is_private_media_path(self, request: Request) -> bool:
        """Limita el transporte por cookie a GET /media/transaction_vouchers/{archivo}."""
        path = request.url.path
        raw = request.scope.get("raw_path", b"")
        raw_path = raw.decode("latin-1") if isinstance(raw, bytes) else str(raw or path)
        if request.method.upper() != "GET":
            return False
        if "//" in path or ".." in path or "%" in raw_path:
            return False
        return bool(_PRIVATE_TRANSACTION_MEDIA_PATTERN.match(path))

    async def _authenticate_token(self, token: str) -> Optional[dict]:
        settings = get_settings()
        mode = settings.AUTH_MODE.lower()
        is_jwt_structure = len(token.split(".")) == 3

        if mode == "jwt":
            return await self._verify_jwt(token)
        elif mode == "dual":
            if is_jwt_structure:
                # Si el token tiene 3 segmentos, es JWT. No hacer fallback/downgrade a opaco si falla.
                return await self._verify_jwt(token)
            return await self._verify_opaque_token_in_database(token)
        else: # legacy
            return await self._verify_opaque_token_in_database(token)

    async def _verify_jwt(self, token: str) -> Optional[dict]:
        """
        Valida un Access Token JWT y comprueba en BD que el usuario y la sesión sigan activos,
        además de verificar que sub y client_app del payload coincidan con la sesión en BD.
        """
        try:
            payload = decode_access_token(token)
            user_id_str = payload.get("sub")
            session_id_str = payload.get("sid")
            client_app_payload = payload.get("client_app")

            if not user_id_str or not session_id_str:
                return None

            user_id = uuid.UUID(user_id_str)
            session_id = uuid.UUID(session_id_str)

            # Verificar estado activo del usuario y sesión en BD
            from app.db.base import AsyncSessionLocal
            from app.modules.auth.infrastructure.auth_session_repository import AuthSessionRepository
            from app.modules.users.domain.models import User as UserModel
            from sqlalchemy.future import select

            async with AsyncSessionLocal() as db_session:
                session_repo = AuthSessionRepository(db_session)
                active = await session_repo.get_active_session_with_user(session_id)
                if not active:
                    return None

                s_model, u_model = active
                # Verificar coincidencia estricta de user_id y client_app entre payload y BD
                if str(s_model.user_id) != user_id_str or s_model.client_app != client_app_payload:
                    logger.warning("JWT claims sub/client_app do not match active session in DB")
                    return None

                if not u_model.enable or u_model.deleted:
                    return None

                # Obtener username del AuthModel
                stmt = select(UserModel.auth_id).where(UserModel.id == user_id)
                res = await db_session.execute(stmt)
                auth_id = res.scalar_one_or_none()

                username = u_model.names or str(u_model.id)
                if auth_id:
                    from app.modules.auth.domain.models import AuthModel
                    a_res = await db_session.execute(select(AuthModel.username).where(AuthModel.id == auth_id))
                    u_name = a_res.scalar_one_or_none()
                    if u_name:
                        username = u_name

                return {
                    "user_id": str(u_model.id),
                    "session_id": str(s_model.id),
                    "username": username,
                    "role": u_model.role or "user",
                    "client_app": s_model.client_app,
                }
        except Exception as e:
            logger.debug(f"JWT verification failed: {e}")
            return None

    async def _verify_token_in_database(self, token: str) -> Optional[dict]:
        return await self._verify_opaque_token_in_database(token)

    async def _verify_opaque_token_in_database(self, token: str) -> Optional[dict]:
        """Valida token opaco en BD (para modos legacy y dual)."""
        try:
            from app.db.base import AsyncSessionLocal
            from sqlalchemy.future import select
            from app.modules.auth.domain.models import AuthModel
            from app.modules.users.domain.models import User as UserModel

            settings = get_settings()
            expiry_minutes = getattr(settings, "TOKEN_EXPIRATION_MINUTES", 1440)

            async with AsyncSessionLocal() as session:
                try:
                    stmt = (
                        select(AuthModel, UserModel)
                        .join(UserModel, UserModel.auth_id == AuthModel.id)
                        .where(AuthModel.token == token, UserModel.deleted.is_(False), UserModel.enable.is_(True))
                    )
                    row = (await session.execute(stmt)).first()

                    if not row:
                        return None

                    auth_model, user_model = row

                    token_created = auth_model.updated_at or auth_model.created_at
                    if token_created:
                        expiry = token_created + timedelta(minutes=expiry_minutes)
                        if datetime.utcnow() > expiry:
                            return None

                    return {
                        "user_id": str(user_model.id),
                        "username": auth_model.username,
                        "role": user_model.role or "user",
                        "created_at": (auth_model.updated_at or datetime.utcnow()).isoformat(),
                    }
                except Exception as e:
                    await session.rollback()
                    logger.error(f"Error in database token verification: {str(e)}")
                    return None
        except Exception as e:
            logger.error(f"Error verifying token in database: {str(e)}")
            return None

    def _is_public_path(self, request: Request | str, method: str = "GET") -> bool:
        """
        Evalúa la allowlist exacta por (método, patrón).
        Rechaza dobles barras, dot-segments y separadores codificados (%2f, %2e, etc.).
        Nunca abre módulos ni prefijos completos por startswith.
        """
        if isinstance(request, str):
            path = request
            raw_path = request
        else:
            method = request.method
            path = request.url.path
            raw = request.scope.get("raw_path", b"")
            raw_path = raw.decode("latin-1") if isinstance(raw, bytes) else str(raw or path)
        method = method.upper()

        if "//" in path or ".." in path or "%" in raw_path:
            return False

        if method == "OPTIONS":
            return True

        if method == "GET" and (
            _PUBLIC_MEDIA_PATTERN.match(path)
            or _LEGACY_PROFILE_MEDIA_PATTERN.match(path)
        ):
            return True

        if (method, path) in _EXACT_PUBLIC_ROUTES:
            return True

        if (method, path) in _LEGACY_ALIAS_PUBLIC_ROUTES:
            return True

        if method == "GET" and (
            _BLOG_SLUG_PATTERN.match(path)
            or _HOME_BANNER_ID_PATTERN.match(path)
            or _HOME_POPUP_ID_PATTERN.match(path)
        ):
            return True

        from app.core.settings import get_settings
        if get_settings().DEBUG and method == "GET" and path in ("/docs", "/redoc", "/openapi.json"):
            return True

        return False
