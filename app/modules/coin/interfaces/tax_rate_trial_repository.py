from app.shared.interface_base import BaseRepositoryInterface
from app.modules.coin.domain.models import TaxRateTrial


class TaxRateTrialRepositoryInterface(BaseRepositoryInterface[TaxRateTrial]):
    """Puerto de persistencia para TaxRateTrial (tasa prueba)."""
