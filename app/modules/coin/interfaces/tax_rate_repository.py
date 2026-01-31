# app/modules/coin/interfaces/tax_rate_repository.py
from app.shared.interface_base import BaseRepositoryInterface
from app.modules.coin.domain.models import TaxRate


class TaxRateRepositoryInterface(BaseRepositoryInterface[TaxRate]):
    """Puerto de persistencia para TaxRate."""
