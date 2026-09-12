from typing import List
from uuid import UUID

from app.shared.interface_base import BaseRepositoryInterface
from app.modules.transactions.domain.models import Tag


class TagRepositoryInterface(BaseRepositoryInterface[Tag]):
    """Puerto de persistencia para el catálogo de etiquetas."""

    async def list_ordered(self, only_active: bool = False) -> List[Tag]:
        """Etiquetas del catálogo ordenadas por posición y nombre."""
        ...

    async def set_transaction_tags(self, transaction_id: UUID, tag_ids: List[UUID]) -> None:
        """Reemplaza (no acumula) las etiquetas de una transacción."""
        ...

    async def tag_ids_by_transaction(self, transaction_ids: List[UUID]) -> dict[UUID, List[UUID]]:
        """Etiquetas por transacción, para hidratar un listado sin N+1."""
        ...
