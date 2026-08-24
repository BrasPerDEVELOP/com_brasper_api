# app/modules/transactions/interfaces/transaction_repository.py
from abc import abstractmethod
from typing import Sequence
from uuid import UUID

from app.shared.interface_base import BaseRepositoryInterface
from app.modules.transactions.domain.models import Transaction


class TransactionRepositoryInterface(BaseRepositoryInterface[Transaction]):
    """Puerto de persistencia para Transaction."""

    @abstractmethod
    async def next_sequential_transaction_code(
        self, origin_currency_code: str, destination_currency_code: str
    ) -> str:
        """Siguiente código `PxB-0000000001` (1ª letra origen + x + 1ª letra destino + secuencia)."""

    @abstractmethod
    async def accounting_percentages(
        self, transaction_ids: Sequence[UUID]
    ) -> dict[UUID, float]:
        """Porcentaje del tramo contable de cada transacción, resuelto al vuelo.

        Solo incluye las transacciones que caen dentro de un tramo: las que no
        (monto por debajo del mínimo del par, o par sin sembrar) se omiten del
        diccionario en lugar de devolver 0.
        """

    @abstractmethod
    async def metrics(self) -> dict:
        """Agregados globales para el dashboard (conteos, volumen, últimos 7 días)."""
