from abc import abstractmethod
from typing import Optional
from uuid import UUID
from app.shared.interface_base import BaseRepositoryInterface
from app.modules.users.domain.models import User


class UserRepositoryInterface(BaseRepositoryInterface[User]):
    """Puerto de persistencia para la entidad *User*."""

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        ...

    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[User]:
        ...

    @abstractmethod
    async def get_by_auth_id(self, auth_id: UUID) -> Optional[User]:
        ...
