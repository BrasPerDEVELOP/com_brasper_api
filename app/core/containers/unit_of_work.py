# app/core/containers/unit_of_work.py
"""Dependencia Unit of Work: una sesión compartida para user y auth."""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.modules.users.infrastructure.unit_of_work import AsyncUserAuthUnitOfWork


async def get_unit_of_work(
    session: AsyncSession = Depends(get_db),
) -> AsyncUserAuthUnitOfWork:
    """Unit of Work para user y auth (misma sesión; commit/rollback unificados)."""
    return AsyncUserAuthUnitOfWork(session)
