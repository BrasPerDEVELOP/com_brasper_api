from __future__ import annotations

from typing import List, Optional, Sequence
from uuid import UUID
from sqlalchemy import select, update, func, or_
import unicodedata
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.domain.models import User, UserIdentification
from app.modules.users.interfaces.user_repository import UserRepositoryInterface
from app.shared.repositorie_base import BaseAsyncRepository


class SQLAlchemyUserRepository(BaseAsyncRepository[User], UserRepositoryInterface):
    def __init__(self, db: AsyncSession):
        super().__init__(User, db)

    async def list_filtered(self, user_id=None, role=None, country=None, search=None):
        stmt = select(User).where(User.deleted.is_(False))
        if user_id is not None:
            stmt = stmt.where(User.id == user_id)
        if role and role.strip():
            stmt = stmt.where(func.lower(User.role) == role.strip().lower())
        if country and country.strip():
            value = ''.join(c for c in unicodedata.normalize('NFD', country.strip().lower())
                            if not unicodedata.combining(c))
            normalized_country = func.translate(func.lower(func.trim(func.coalesce(User.country, ''))),
                                                'áéíóúüñ', 'aeiouun')
            stmt = stmt.where(normalized_country == ('' if value == 'sin-pais' else value))
        if search and search.strip():
            value = search.strip()
            full_name = func.trim(func.coalesce(User.names, '') + ' ' + func.coalesce(User.lastnames, ''))
            stmt = stmt.where(or_(
                full_name.icontains(value, autoescape=True),
                User.email.icontains(value, autoescape=True),
                User.document_number.icontains(value, autoescape=True),
                User.identifications.any(
                    (UserIdentification.deleted.is_(False)) & or_(
                        UserIdentification.document_number.icontains(value, autoescape=True),
                        UserIdentification.document_type.icontains(value, autoescape=True),
                    )
                ),
            ))
        result = await self.session.execute(stmt.order_by(User.names.asc(), User.lastnames.asc(), User.id.asc()))
        return list(result.scalars().all())

    async def list_countries(self, role=None):
        country = func.trim(User.country)
        stmt = select(country).where(User.deleted.is_(False), country.is_not(None), country != '')
        if role and role.strip():
            stmt = stmt.where(func.lower(User.role) == role.strip().lower())
        result = await self.session.execute(stmt.distinct().order_by(country))
        return list(result.scalars().all())

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        return await self.get(user_id)

    async def soft_delete_identifications(self, user_id: UUID) -> None:
        """Marca como borradas las identificaciones del usuario.

        Acompaña al borrado lógico del usuario: el índice único de
        `(document_type, document_number)` solo mira las filas vivas, así que si
        estas no se marcan, el documento queda bloqueado para siempre.
        """
        await self.session.execute(
            update(UserIdentification)
            .where(
                UserIdentification.user_id == user_id,
                UserIdentification.deleted.is_(False),
            )
            .values(deleted=True)
        )

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
