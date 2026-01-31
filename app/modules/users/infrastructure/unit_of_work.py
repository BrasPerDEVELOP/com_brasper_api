# app/modules/users/infrastructure/unit_of_work.py
"""Implementación del Unit of Work para user y auth (una sesión, un commit/rollback)."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.unit_of_work import UnitOfWorkBase
from app.modules.users.interfaces.user_repository import UserRepositoryInterface
from app.modules.auth.interfaces.auth_repository import AuthRepositoryInterface
from app.modules.users.infrastructure.repository import SQLAlchemyUserRepository
from app.modules.auth.infrastructure.repository import SQLAlchemyAuthRepository


class AsyncUserAuthUnitOfWork(UnitOfWorkBase):
    """Unit of Work: una sesión compartida por user y auth; commit/rollback unificados."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._user_repository: UserRepositoryInterface | None = None
        self._auth_repository: AuthRepositoryInterface | None = None

    @property
    def user_repository(self) -> UserRepositoryInterface:
        if self._user_repository is None:
            self._user_repository = SQLAlchemyUserRepository(self._session)
        return self._user_repository

    @property
    def auth_repository(self) -> AuthRepositoryInterface:
        if self._auth_repository is None:
            self._auth_repository = SQLAlchemyAuthRepository(self._session)
        return self._auth_repository

    @property
    def session(self) -> AsyncSession:
        return self._session

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
