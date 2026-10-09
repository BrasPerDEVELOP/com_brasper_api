from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.modules.transactions.domain.models import Coupon
from app.modules.transactions.interfaces.coupon_repository import CouponRepositoryInterface
from app.shared.repositorie_base import BaseAsyncRepository


class SQLAlchemyCouponRepository(
    BaseAsyncRepository[Coupon], CouponRepositoryInterface
):
    def __init__(self, db: AsyncSession):
        super().__init__(Coupon, db)

    async def get_for_update(self, coupon_id):
        return (await self.session.execute(select(Coupon).where(
            Coupon.id == coupon_id, Coupon.deleted.is_(False)).with_for_update()
            .execution_options(populate_existing=True))).scalar_one_or_none()
