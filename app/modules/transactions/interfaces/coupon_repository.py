from app.shared.interface_base import BaseRepositoryInterface
from app.modules.transactions.domain.models import Coupon


class CouponRepositoryInterface(BaseRepositoryInterface[Coupon]):
    """Puerto de persistencia para Coupon."""
