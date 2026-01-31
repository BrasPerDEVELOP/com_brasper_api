from app.shared.interface_base import BaseRepositoryInterface
from app.modules.transactions.domain.models import BankAccount


class BankAccountRepositoryInterface(BaseRepositoryInterface[BankAccount]):
    """Puerto de persistencia para BankAccount."""
