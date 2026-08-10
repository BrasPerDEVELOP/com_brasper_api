"""Casos de uso del catálogo de etiquetas de transacción."""
from typing import List, Optional
from uuid import UUID

from app.modules.transactions.application.schemas.tag_schema import (
    TagCreateCmd,
    TagReadDTO,
    TagUpdateCmd,
)
from app.modules.transactions.domain.models import Tag
from app.modules.transactions.interfaces.tag_repository import TagRepositoryInterface


class ListTagsUseCase:
    def __init__(self, repo: TagRepositoryInterface):
        self.repo = repo

    async def execute(self, only_active: bool = False) -> List[TagReadDTO]:
        entities = await self.repo.list_ordered(only_active=only_active)
        return [TagReadDTO.from_tag(e) for e in entities]


class GetTagByIdUseCase:
    def __init__(self, repo: TagRepositoryInterface):
        self.repo = repo

    async def execute(self, tag_id: UUID) -> Optional[TagReadDTO]:
        entity = await self.repo.get(tag_id)
        return TagReadDTO.from_tag(entity) if entity else None


class CreateTagUseCase:
    def __init__(self, repo: TagRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: TagCreateCmd) -> TagReadDTO:
        existing = await self.repo.list_ordered()
        if any(e.label.strip().lower() == cmd.label.lower() for e in existing):
            raise ValueError(f"Ya existe una etiqueta llamada «{cmd.label}»")

        entity = Tag(
            label=cmd.label,
            color=cmd.color,
            active=cmd.active,
            counts_as_new_client=cmd.counts_as_new_client,
            position=cmd.position,
        )
        saved = await self.repo.add(entity)
        # El flag es exclusivo: si esta lo trae, se lo quitamos a las demás.
        if cmd.counts_as_new_client:
            await self.repo.clear_new_client_flag(except_id=saved.id)
        await self.repo.commit()
        await self.repo.refresh(saved)
        return TagReadDTO.from_tag(saved)


class UpdateTagUseCase:
    def __init__(self, repo: TagRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: TagUpdateCmd) -> Optional[TagReadDTO]:
        entity = await self.repo.get(cmd.id)
        if not entity:
            return None

        if cmd.label is not None:
            existing = await self.repo.list_ordered()
            clashes = any(
                e.id != cmd.id and e.label.strip().lower() == cmd.label.lower()
                for e in existing
            )
            if clashes:
                raise ValueError(f"Ya existe una etiqueta llamada «{cmd.label}»")
            entity.label = cmd.label
        if cmd.color is not None:
            entity.color = cmd.color
        if cmd.active is not None:
            entity.active = cmd.active
        if cmd.position is not None:
            entity.position = cmd.position
        if cmd.counts_as_new_client is not None:
            entity.counts_as_new_client = cmd.counts_as_new_client
            if cmd.counts_as_new_client:
                await self.repo.clear_new_client_flag(except_id=cmd.id)

        await self.repo.update(entity)
        await self.repo.commit()
        await self.repo.refresh(entity)
        return TagReadDTO.from_tag(entity)


class DeleteTagUseCase:
    def __init__(self, repo: TagRepositoryInterface):
        self.repo = repo

    async def execute(self, tag_id: UUID) -> None:
        """Borra la etiqueta del catálogo.

        El borrado es lógico (`deleted=True`), igual que en el resto del API. Las
        transacciones dejan de mostrarla porque `tag_ids_by_transaction` filtra
        por `Tag.deleted`, así que no hace falta limpiar el puente a mano.
        """
        await self.repo.delete(tag_id)
        await self.repo.commit()
