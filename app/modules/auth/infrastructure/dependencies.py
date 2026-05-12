# app/modules/auth/infrastructure/dependencies.py
# Inyección de dependencias para el módulo auth (repos, security, current user).
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import SecurityUtils
from app.core.settings import get_settings
from app.core.oauth2_scheme import oauth2_scheme
from app.db.base import get_db
from app.modules.auth.domain.models import RolePermissionModel
from app.modules.auth.domain.permissions import default_permissions_for_role
from app.modules.auth.infrastructure.repository import SQLAlchemyAuthRepository
from app.modules.auth.interfaces.auth_repository import AuthRepositoryInterface
from app.modules.users.domain.models import User


def get_security_utils() -> SecurityUtils:
    return SecurityUtils(get_settings())


async def get_auth_repository(
    db: AsyncSession = Depends(get_db),
) -> AuthRepositoryInterface:
    return SQLAlchemyAuthRepository(db)


def get_current_user() -> dict:
    """Obtiene el usuario actual desde el middleware."""
    from app.middlewares.auth import get_current_user as get_user
    user = get_user()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user  # type: ignore[return-value]


def get_current_token() -> str:
    """Obtiene el token actual desde el middleware."""
    from app.middlewares.auth import get_current_token as get_token
    token = get_token()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token  # type: ignore[return-value]


async def require_auth(
    current_user: dict = Depends(get_current_user),
    _oauth2_token: Optional[str] = Depends(oauth2_scheme),
):
    return current_user


async def require_token(token: str = Depends(get_current_token)):
    return token


async def get_current_user_permissions(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    user_id = current_user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    result = await db.execute(select(User).where(User.id == UUID(str(user_id)), User.deleted.is_(False)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    role_result = await db.execute(
        select(RolePermissionModel).where(
            RolePermissionModel.role == user.role,
            RolePermissionModel.deleted.is_(False),
            RolePermissionModel.enable.is_(True),
        )
    )
    role_permissions = role_result.scalar_one_or_none()
    if role_permissions and role_permissions.permissions:
        return list(role_permissions.permissions)
    return default_permissions_for_role(user.role)


def require_permission(permission: str):
    async def dependency(
        permissions: list[str] = Depends(get_current_user_permissions),
    ) -> list[str]:
        if permission not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permiso requerido: {permission}",
            )
        return permissions

    return dependency
