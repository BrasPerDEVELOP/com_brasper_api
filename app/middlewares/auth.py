import logging
from typing import Optional
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from contextvars import ContextVar
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

current_user_var = ContextVar("current_user", default=None)
current_token_var = ContextVar("current_token", default=None)


def get_current_user() -> Optional[dict]:
    return current_user_var.get()


def get_current_token() -> Optional[str]:
    return current_token_var.get()


class TokenAuthMiddleware(BaseHTTPMiddleware):
    """Middleware para autenticación con tokens opacos (validación vía BD)."""

    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        current_user_var.set(None)
        current_token_var.set(None)

        if self._is_public_path(request.url.path):
            return await call_next(request)

        token = self._extract_token(request)
        if not token:
            logger.debug(f"No token provided for path: {request.url.path}")
            return await call_next(request)

        # Validar token opaco solo por BD (lookup por token + expiración)
        user_data = await self._verify_token_in_database(token)

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
        """Extrae el token del header Authorization"""
        authorization = request.headers.get("Authorization")
        if not authorization:
            return None
        
        if authorization.startswith("Bearer "):
            return authorization[7:]
        
        return None
    
    async def _verify_token_in_database(self, token: str) -> Optional[dict]:
        """Valida token opaco: lookup en auth_login por token, comprueba expiración y devuelve datos de usuario."""
        try:
            from app.db.base import AsyncSessionLocal
            from sqlalchemy.future import select
            from app.modules.auth.domain.models import AuthModel
            from app.modules.users.domain.models import User as UserModel
            from app.core.settings import get_settings

            settings = get_settings()
            expiry_minutes = getattr(settings, "TOKEN_EXPIRATION_MINUTES", 1440)

            async with AsyncSessionLocal() as session:
                try:
                    stmt = select(AuthModel).where(AuthModel.token == token)
                    result = await session.execute(stmt)
                    auth_model = result.scalars().first()

                    if not auth_model:
                        logger.debug("Token not found in database")
                        return None

                    # Expiración: el token se guardó en updated_at; válido hasta updated_at + TOKEN_EXPIRATION_MINUTES
                    token_created = auth_model.updated_at or auth_model.created_at
                    if token_created:
                        expiry = token_created + timedelta(minutes=expiry_minutes)
                        if datetime.utcnow() > expiry:
                            logger.debug("Token expired")
                            return None

                    user_stmt = select(UserModel).where(
                        UserModel.auth_id == auth_model.id,
                        UserModel.deleted.is_(False)
                    )
                    user_result = await session.execute(user_stmt)
                    user_model = user_result.scalar_one_or_none()

                    if not user_model:
                        logger.debug("User not found for auth_id")
                        return None

                    return {
                        "user_id": str(user_model.id),
                        "username": auth_model.username,
                        "created_at": (auth_model.updated_at or datetime.utcnow()).isoformat(),
                    }
                except Exception as e:
                    await session.rollback()
                    logger.error(f"Error in database token verification: {str(e)}")
                    return None
        except Exception as e:
            logger.error(f"Error verifying token in database: {str(e)}")
            return None
    
    def _is_public_path(self, path: str) -> bool:
        """Define rutas públicas que no requieren autenticación"""
        public_paths = [
            "/auth/",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/",
        ]
        
        return any(path.startswith(p) for p in public_paths)
