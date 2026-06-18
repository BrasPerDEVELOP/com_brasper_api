from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.middlewares.auth import get_current_user
from app.modules.auth.domain.models import RolePermissionModel
from app.modules.users.domain.models import User


def require_permission(permission: str) -> Callable:
    async def dependency(db: AsyncSession = Depends(get_db)) -> None:
        current = get_current_user()
        if not current or not current.get("user_id"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticación requerida")
        user = await db.get(User, UUID(current["user_id"]))
        if not user or user.deleted:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado")
        role = user.role or "user"
        permissions = (await db.execute(select(RolePermissionModel.permissions).where(
            RolePermissionModel.role == role, RolePermissionModel.deleted.is_(False), RolePermissionModel.enable.is_(True)
        ))).scalar_one_or_none() or []
        if permission not in permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Permiso requerido: {permission}")
    return dependency
