from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.transactions.domain.models import Coupon
from app.modules.transactions.interfaces.coupon_repository import CouponRepositoryInterface
from app.shared.repositorie_base import BaseAsyncRepository


class SQLAlchemyCouponRepository(
    BaseAsyncRepository[Coupon], CouponRepositoryInterface
):
    def __init__(self, db: AsyncSession):
        super().__init__(Coupon, db)
