# app/modules/transactions/adapters/router/tag_routes.py
"""Catálogo de etiquetas que ventas aplica a las transacciones."""
from typing import List
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

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

router = APIRouter(prefix="/tags", tags=["transaction-tags"])


@router.get("/", response_model=List[TagReadDTO])
async def list_tags(
    use_case: ListTagsUseCaseDep,
    only_active: bool = Query(
        False,
        description="Solo etiquetas activas (las que se ofrecen al registrar)",
    ),
):
    """Catálogo ordenado por posición y nombre."""
    return await use_case.execute(only_active=only_active)


@router.get("/{tag_id}", response_model=TagReadDTO)
async def get_tag_by_id(tag_id: UUID, use_case: GetTagByIdUseCaseDep):
    entity = await use_case.execute(tag_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Etiqueta no encontrada")
    return entity


@router.post("/", response_model=TagReadDTO, status_code=status.HTTP_201_CREATED)
async def create_tag(cmd: TagCreateCmd, use_case: CreateTagUseCaseDep):
    try:
        return await use_case.execute(cmd)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/", response_model=TagReadDTO)
async def update_tag(cmd: TagUpdateCmd, use_case: UpdateTagUseCaseDep):
    try:
        entity = await use_case.execute(cmd)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not entity:
        raise HTTPException(status_code=404, detail="Etiqueta no encontrada")
    return entity


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(tag_id: UUID, use_case: DeleteTagUseCaseDep):
    await use_case.execute(tag_id)
