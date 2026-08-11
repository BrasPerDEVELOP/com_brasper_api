# app/modules/transactions/adapters/router/tag_routes.py
"""Catálogo de etiquetas que ventas aplica a las transacciones."""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.modules.transactions.application.schemas import (
    TagCreateCmd,
    TagReadDTO,
    TagUpdateCmd,
)
from app.modules.transactions.adapters.dependencies import (
    ListTagsUseCaseDep,
    GetTagByIdUseCaseDep,
    CreateTagUseCaseDep,
    UpdateTagUseCaseDep,
    DeleteTagUseCaseDep,
)

from app.core.routing import LegacyAliasRouter
from app.modules.auth.infrastructure.dependencies import require_permission

router = LegacyAliasRouter(prefix="/tags", tags=["transaction-tags"])


@router.get("", response_model=List[TagReadDTO])
async def list_tags(
    use_case: ListTagsUseCaseDep,
    only_active: bool = Query(
        False,
        description="Solo etiquetas activas (las que se ofrecen al registrar)",
    ),
    _permissions=Depends(require_permission("tags.view")),
):
    """Catálogo ordenado por posición y nombre."""
    return await use_case.execute(only_active=only_active)


@router.get("/{tag_id}", response_model=TagReadDTO)
async def get_tag_by_id(
    tag_id: UUID,
    use_case: GetTagByIdUseCaseDep,
    _permissions=Depends(require_permission("tags.view")),
):
    entity = await use_case.execute(tag_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Etiqueta no encontrada")
    return entity


from app.modules.audit.infrastructure.stage_mutation_audit import stage_mutation_audit


@router.post("", response_model=TagReadDTO, status_code=status.HTTP_201_CREATED)
async def create_tag(
    cmd: TagCreateCmd,
    use_case: CreateTagUseCaseDep,
    _permissions=Depends(require_permission("tags.create")),
    audit_event=Depends(stage_mutation_audit("transaction_tags.create", "transaction_tag")),
):
    try:
        created = await use_case.execute(cmd)
        if audit_event and created:
            audit_event.entity_id = str(created.id)
            audit_event.new_values = cmd.model_dump(mode="json")
        return created
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("", response_model=TagReadDTO)
async def update_tag(
    cmd: TagUpdateCmd,
    use_case: UpdateTagUseCaseDep,
    get_use_case: GetTagByIdUseCaseDep,
    _permissions=Depends(require_permission("tags.update")),
    audit_event=Depends(stage_mutation_audit("transaction_tags.update", "transaction_tag")),
):
    try:
        previous = await get_use_case.execute(cmd.id)
        if audit_event and previous:
            audit_event.old_values = previous.model_dump(mode="json")
        entity = await use_case.execute(cmd)
        if audit_event and entity:
            audit_event.entity_id = str(entity.id)
            audit_event.new_values = cmd.model_dump(mode="json")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not entity:
        raise HTTPException(status_code=404, detail="Etiqueta no encontrada")
    return entity


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: UUID,
    use_case: DeleteTagUseCaseDep,
    get_use_case: GetTagByIdUseCaseDep,
    _permissions=Depends(require_permission("tags.delete")),
    audit_event=Depends(stage_mutation_audit("transaction_tags.delete", "transaction_tag")),
):
    previous = await get_use_case.execute(tag_id)
    if audit_event:
        audit_event.entity_id = str(tag_id)
        audit_event.old_values = previous.model_dump(mode="json") if previous else None
    await use_case.execute(tag_id)
