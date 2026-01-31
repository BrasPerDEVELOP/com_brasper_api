# app/modules/coin/interfaces/commission_repository.py
from app.shared.interface_base import BaseRepositoryInterface
from app.modules.coin.domain.models import Commission


class CommissionRepositoryInterface(BaseRepositoryInterface[Commission]):
    """Puerto de persistencia para Commission."""
