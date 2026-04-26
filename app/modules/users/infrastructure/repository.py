from __future__ import annotations

from typing import List, Optional, Sequence
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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

    async def list_ids_by_roles(self, roles: Sequence[str]) -> List[UUID]:
        role_values = tuple(r for r in roles if r and str(r).strip())
        if not role_values:
            return []
        stmt = select(User.id).where(
            User.role.in_(role_values),
            User.deleted.is_(False),
            User.enable.is_(True),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
