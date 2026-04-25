from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.brasper.domain.models import ContacForm
from app.modules.brasper.interfaces.contact_form_repository import ContactFormRepositoryInterface
from app.shared.repositorie_base import BaseAsyncRepository


class SQLAlchemyContactFormRepository(BaseAsyncRepository[ContacForm], ContactFormRepositoryInterface):
    def __init__(self, db: AsyncSession):
        super().__init__(ContacForm, db)
