# app/modules/coin/interfaces/commission_accounting_repository.py
from app.shared.interface_base import BaseRepositoryInterface
from app.modules.coin.domain.models import CommissionAccounting


class CommissionAccountingRepositoryInterface(BaseRepositoryInterface[CommissionAccounting]):
    """Puerto de persistencia para CommissionAccounting."""
