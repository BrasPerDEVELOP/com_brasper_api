# app/modules/integraciones/infrastructure/repository.py
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integraciones.domain.models import Integration, SocialAccount
from app.modules.integraciones.interfaces.integration_repository import IntegrationRepositoryInterface
from app.modules.integraciones.interfaces.social_account_repository import SocialAccountRepositoryInterface
from app.shared.repositorie_base import BaseAsyncRepository


class SQLAlchemyIntegrationRepository(BaseAsyncRepository[Integration], IntegrationRepositoryInterface):
    def __init__(self, db: AsyncSession):
        super().__init__(Integration, db)

    async def get_by_provider(self, provider: str) -> Optional[Integration]:
        stmt = (
            select(Integration)
            .where(
                Integration.provider == provider,
                Integration.deleted.is_(False),
                Integration.enable.is_(True),
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class SQLAlchemySocialAccountRepository(
    BaseAsyncRepository[SocialAccount], SocialAccountRepositoryInterface
):
    def __init__(self, db: AsyncSession):
        super().__init__(SocialAccount, db)

    async def get_by_provider_and_provider_user_id(
        self, provider: str, provider_user_id: str
    ) -> Optional[SocialAccount]:
        stmt = (
            select(SocialAccount)
            .where(
                SocialAccount.provider == provider,
                SocialAccount.provider_user_id == provider_user_id,
                SocialAccount.deleted.is_(False),
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
