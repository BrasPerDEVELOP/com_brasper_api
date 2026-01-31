from app.shared.interface_base import BaseRepositoryInterface
from app.modules.transactions.domain.models import Bank


class BankRepositoryInterface(BaseRepositoryInterface[Bank]):
    """Puerto de persistencia para Bank."""
