from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.transactions.domain.models import Tag, TransactionTag
from app.modules.transactions.interfaces.tag_repository import TagRepositoryInterface
from app.shared.repositorie_base import BaseAsyncRepository


class SQLAlchemyTagRepository(BaseAsyncRepository[Tag], TagRepositoryInterface):
    def __init__(self, db: AsyncSession):
        super().__init__(Tag, db)

    async def list_ordered(self, only_active: bool = False) -> List[Tag]:
        stmt = select(Tag).where(Tag.deleted.is_(False))
        if only_active:
            stmt = stmt.where(Tag.active.is_(True))
        stmt = stmt.order_by(Tag.position, Tag.label)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def clear_new_client_flag(self, except_id: UUID | None = None) -> None:
        """Solo una etiqueta puede contar como «cliente nuevo»."""
        stmt = update(Tag).where(Tag.counts_as_new_client.is_(True))
        if except_id is not None:
            stmt = stmt.where(Tag.id != except_id)
        await self.session.execute(stmt.values(counts_as_new_client=False))

    async def set_transaction_tags(self, transaction_id: UUID, tag_ids: List[UUID]) -> None:
        """Reemplaza las etiquetas de la transacción.

        A diferencia de los comprobantes (que se acumulan), las etiquetas son una
        lista autoritativa: lo que llega es exactamente lo que queda.
        """
        await self.session.execute(
            delete(TransactionTag).where(TransactionTag.transaction_id == transaction_id)
        )
        seen: set[UUID] = set()
        for tag_id in tag_ids:
            if tag_id in seen:
                continue
            seen.add(tag_id)
            self.session.add(TransactionTag(transaction_id=transaction_id, tag_id=tag_id))
        await self.session.flush()

    async def tag_ids_by_transaction(
        self, transaction_ids: List[UUID]
    ) -> dict[UUID, List[UUID]]:
        if not transaction_ids:
            return {}
        stmt = (
            select(TransactionTag.transaction_id, TransactionTag.tag_id, Tag.position, Tag.label)
            .join(Tag, Tag.id == TransactionTag.tag_id)
            .where(
                TransactionTag.transaction_id.in_(transaction_ids),
                TransactionTag.deleted.is_(False),
                Tag.deleted.is_(False),
            )
            .order_by(Tag.position, Tag.label)
        )
        result = await self.session.execute(stmt)
        grouped: dict[UUID, List[UUID]] = {}
        for transaction_id, tag_id, _position, _label in result.all():
            grouped.setdefault(transaction_id, []).append(tag_id)
        return grouped
