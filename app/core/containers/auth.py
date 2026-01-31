# app/core/containers/auth.py
"""Inyección de dependencias del módulo auth."""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.modules.auth.interfaces.auth_repository import AuthRepositoryInterface
from app.modules.auth.infrastructure.repository import SQLAlchemyAuthRepository
from app.modules.auth.application.auth_service import AuthService
from app.modules.auth.application.use_cases import LoginUseCase
from app.core.containers.common import get_security_utils
from app.core.containers.unit_of_work import get_unit_of_work
from app.modules.users.infrastructure.unit_of_work import AsyncUserAuthUnitOfWork


async def get_auth_repository(
    db: AsyncSession = Depends(get_db),
) -> AuthRepositoryInterface:
    """Repositorio de autenticación (auth_login)."""
    return SQLAlchemyAuthRepository(db)


def get_login_uc(
    uow: AsyncUserAuthUnitOfWork = Depends(get_unit_of_work),
    security_utils=Depends(get_security_utils),
) -> LoginUseCase:
    """Caso de uso de login (usa Unit of Work)."""
    return LoginUseCase(uow, security_utils)


def get_auth_service(
    uow: AsyncUserAuthUnitOfWork = Depends(get_unit_of_work),
    security_utils=Depends(get_security_utils),
) -> AuthService:
    """Servicio de auth para change_password, reset (usa Unit of Work)."""
    return AuthService(uow, security_utils)
