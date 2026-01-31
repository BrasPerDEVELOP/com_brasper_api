# app/modules/transactions/interfaces/transaction_repository.py
from app.shared.interface_base import BaseRepositoryInterface
from app.modules.transactions.domain.models import Transaction


class TransactionRepositoryInterface(BaseRepositoryInterface[Transaction]):
    """Puerto de persistencia para Transaction."""
