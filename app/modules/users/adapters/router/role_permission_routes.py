from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, status

from app.db.base import get_db
from app.modules.auth.domain.models import RolePermissionModel
from app.modules.auth.domain.permissions import ALL_PERMISSIONS, default_permissions_for_role
from app.modules.auth.infrastructure.dependencies import require_permission
from app.modules.users.domain.enums import UserRole

router = APIRouter(prefix="/roles", tags=["roles"])


class RolePermissionsDTO(BaseModel):
    role: UserRole
    permissions: list[str]


class RolePermissionsUpdateRequest(BaseModel):
    permissions: list[str] = Field(default_factory=list)

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, value: list[str]) -> list[str]:
        allowed = set(ALL_PERMISSIONS)
        invalid = [permission for permission in value if permission not in allowed]
        if invalid:
            raise ValueError(f"Permisos inválidos: {', '.join(invalid)}")
        return list(dict.fromkeys(value))


async def _get_role_permission(
    db: AsyncSession,
    role: UserRole,
) -> RolePermissionModel | None:
    result = await db.execute(
        select(RolePermissionModel).where(
            RolePermissionModel.role == role.value,
            RolePermissionModel.deleted.is_(False),
        )
    )
    return result.scalar_one_or_none()


@router.get("/permissions/", response_model=list[RolePermissionsDTO])
async def list_role_permissions(
    _permissions=Depends(require_permission("roles.permissions.view")),
    db: AsyncSession = Depends(get_db),
):
    rows = {}
    result = await db.execute(
        select(RolePermissionModel).where(RolePermissionModel.deleted.is_(False))
    )
    for row in result.scalars().all():
        rows[row.role] = row.permissions

    return [
        RolePermissionsDTO(
            role=role,
            permissions=rows.get(role.value) or default_permissions_for_role(role.value),
        )
        for role in UserRole
    ]


@router.put("/{role}/permissions/", response_model=RolePermissionsDTO)
async def update_role_permissions(
    role: UserRole,
    request: RolePermissionsUpdateRequest,
    _permissions=Depends(require_permission("roles.permissions.update")),
    db: AsyncSession = Depends(get_db),
):
    if role == UserRole.admin:
        critical = {"roles.permissions.view", "roles.permissions.update"}
        if not critical.issubset(set(request.permissions)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin debe conservar permisos críticos de roles",
            )

    row = await _get_role_permission(db, role)
    if row is None:
        row = RolePermissionModel(
            role=role.value,
            permissions=request.permissions,
        )
        db.add(row)
    else:
        row.permissions = request.permissions
        row.enable = True

    await db.commit()
    await db.refresh(row)
    return RolePermissionsDTO(role=role, permissions=row.permissions)
