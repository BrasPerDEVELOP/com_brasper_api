from __future__ import annotations

from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.modules.users.domain.models import User
from app.modules.users.interfaces.user_repository import UserRepositoryInterface
from app.shared.repositorie_base import BaseAsyncRepository


class SQLAlchemyUserRepository(BaseAsyncRepository[User], UserRepositoryInterface):
    def __init__(self, db: AsyncSession):
        super().__init__(User, db)

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        return await self.get(user_id)

    async def get_by_email(self, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email, User.deleted.is_(False))
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_auth_id(self, auth_id: UUID) -> Optional[User]:
        stmt = select(User).where(User.auth_id == auth_id, User.deleted.is_(False))
        result = await self.session.execute(stmt)
        return result.scalars().first()
