from app.shared.interface_base import BaseRepositoryInterface
from app.modules.transactions.domain.models import Coupon


class CouponRepositoryInterface(BaseRepositoryInterface[Coupon]):
    """Puerto de persistencia para Coupon."""

    async def get_for_update(self, coupon_id):
        raise NotImplementedError
