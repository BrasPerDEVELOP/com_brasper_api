# app/core/containers/users.py
"""Inyección de dependencias del módulo users: repositorio y casos de uso."""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.modules.users.interfaces.user_repository import UserRepositoryInterface
from app.modules.users.infrastructure.repository import SQLAlchemyUserRepository
from app.modules.users.infrastructure.unit_of_work import AsyncUserAuthUnitOfWork
from app.modules.users.application.use_cases import (
    GetUserByIdUseCase,
    GetUserByEmailUseCase,
    GetUserByAuthIdUseCase,
    CreateUserUseCase,
    UpdateUserUseCase,
    DeleteUserUseCase,
    ListUserUseCase,
    ListUserNameUseCase,
    ListUsersWithDetailsUseCase,
)
from app.core.containers.common import get_security_utils
from app.core.containers.unit_of_work import get_unit_of_work
from app.modules.auth.application.use_cases import CreateAuthService


def get_user_repository(
    db: AsyncSession = Depends(get_db),
) -> UserRepositoryInterface:
    """Repositorio de usuarios (user.user)."""
    return SQLAlchemyUserRepository(db)


# --- Casos de uso solo lectura (usan repo) ---

def get_user_by_id_uc(db: AsyncSession = Depends(get_db)) -> GetUserByIdUseCase:
    return GetUserByIdUseCase(get_user_repository(db))


def get_user_by_email_uc(db: AsyncSession = Depends(get_db)) -> GetUserByEmailUseCase:
    return GetUserByEmailUseCase(get_user_repository(db))


def get_user_by_auth_id_uc(db: AsyncSession = Depends(get_db)) -> GetUserByAuthIdUseCase:
    return GetUserByAuthIdUseCase(get_user_repository(db))


def list_user_name_uc(db: AsyncSession = Depends(get_db)) -> ListUserNameUseCase:
    return ListUserNameUseCase(get_user_repository(db))


def list_users_uc(db: AsyncSession = Depends(get_db)) -> ListUserUseCase:
    return ListUserUseCase(get_user_repository(db))


def list_users_with_details_uc(db: AsyncSession = Depends(get_db)) -> ListUsersWithDetailsUseCase:
    return ListUsersWithDetailsUseCase(get_user_repository(db))


# --- Casos de uso escritura (usan Unit of Work) ---

async def create_user_uc(
    uow: AsyncUserAuthUnitOfWork = Depends(get_unit_of_work),
    security_utils=Depends(get_security_utils),
) -> CreateUserUseCase:
    auth_service = CreateAuthService(security_utils, uow.auth_repository)
    return CreateUserUseCase(uow, auth_service)


def update_user_uc(
    uow: AsyncUserAuthUnitOfWork = Depends(get_unit_of_work),
) -> UpdateUserUseCase:
    return UpdateUserUseCase(uow)


def delete_user_uc(
    uow: AsyncUserAuthUnitOfWork = Depends(get_unit_of_work),
) -> DeleteUserUseCase:
    return DeleteUserUseCase(uow)
