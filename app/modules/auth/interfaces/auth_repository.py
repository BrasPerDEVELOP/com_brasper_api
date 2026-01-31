# com_build_api/app/auth/interfaces/auth_repository.py
from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from app.modules.auth.domain.credentials import Credentials

class AuthRepositoryInterface(ABC):
    @abstractmethod
    async def get_by_id(self, auth_id: UUID) -> Optional[Credentials]:
        pass
    
    @abstractmethod
    async def get_by_username(self, username: str) -> Optional[Credentials]:
        pass
    
    @abstractmethod
    async def create(self, credentials: Credentials) -> Credentials:
        pass
    
    @abstractmethod
    async def update_token(self, auth_id: UUID, token: Optional[str] = None) -> bool:
        pass
    
    @abstractmethod
    async def get_by_token(self, token: str) -> Optional[Credentials]:
        pass
    
    @abstractmethod
    async def update_password(self, auth_id: UUID, hashed_password: str) -> bool:
        pass
    
    @abstractmethod
    async def update_recovery_code(self, auth_id: UUID, recovery_code: Optional[str]) -> bool:
        pass

    @abstractmethod
    async def delete(self, auth_id: UUID) -> bool:
        pass
