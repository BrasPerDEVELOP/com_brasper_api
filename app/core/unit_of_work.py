# app/core/unit_of_work.py
"""Unit of Work: transacción única para user y auth (una sesión, un commit/rollback)."""
from abc import ABC, abstractmethod
from typing import Protocol

from app.modules.auth.interfaces.auth_repository import AuthRepositoryInterface
from app.modules.users.interfaces.user_repository import UserRepositoryInterface


class UnitOfWorkInterface(Protocol):
    """Contrato del Unit of Work: repos compartidos y control de transacción."""

    @property
    def user_repository(self) -> UserRepositoryInterface: ...

    @property
    def auth_repository(self) -> AuthRepositoryInterface: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class UnitOfWorkBase(ABC):
    """Base abstracta para implementaciones de Unit of Work."""

    @property
    @abstractmethod
    def user_repository(self) -> UserRepositoryInterface: ...

    @property
    @abstractmethod
    def auth_repository(self) -> AuthRepositoryInterface: ...

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...
