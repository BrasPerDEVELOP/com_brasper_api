# app/modules/transactions/interfaces/transaction_repository.py
from abc import abstractmethod

from app.shared.interface_base import BaseRepositoryInterface
from app.modules.transactions.domain.models import Transaction


class TransactionRepositoryInterface(BaseRepositoryInterface[Transaction]):
    """Puerto de persistencia para Transaction."""

    @abstractmethod
    async def next_sequential_transaction_code(
        self, origin_currency_code: str, destination_currency_code: str
    ) -> str:
        """Siguiente código `ORIGEN-DEST-0000000001` para el par de monedas (orden global en BD)."""
