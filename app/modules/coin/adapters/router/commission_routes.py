# app/modules/coin/adapters/router/commission_routes.py
from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from typing import List

from app.modules.coin.application.schemas import (
    CommissionCreateCmd,
    CommissionUpdateCmd,
    CommissionReadDTO,
)
from app.modules.coin.adapters.dependencies import (
    GetCommissionByIdUseCaseDep,
    ListCommissionsUseCaseDep,
    CreateCommissionUseCaseDep,
    UpdateCommissionUseCaseDep,
    DeleteCommissionUseCaseDep,
)

from app.core.routing import LegacyAliasRouter
from app.modules.auth.infrastructure.dependencies import require_permission

router = LegacyAliasRouter(prefix="/commission", tags=["commission"])


@router.get("", response_model=List[CommissionReadDTO])
async def list_commissions(use_case: ListCommissionsUseCaseDep):
    return await use_case.execute()


@router.get("/{commission_id}", response_model=CommissionReadDTO)
async def get_commission_by_id(
    commission_id: UUID,
    use_case: GetCommissionByIdUseCaseDep,
    _permissions=Depends(require_permission("commissions.view")),
):
    entity = await use_case.execute(commission_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Comisión no encontrada")
    return entity


from app.modules.audit.infrastructure.stage_mutation_audit import stage_mutation_audit


@router.post("", response_model=CommissionReadDTO, status_code=status.HTTP_201_CREATED)
async def create_commission(
    cmd: CommissionCreateCmd,
    use_case: CreateCommissionUseCaseDep,
    _permissions=Depends(require_permission("commissions.create")),
    audit_event=Depends(stage_mutation_audit("commission.create", "commission")),
):
    try:
        created = await use_case.execute(cmd)
        if audit_event and created:
            audit_event.entity_id = str(created.id)
            audit_event.new_values = cmd.model_dump(mode="json")
        return created
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("", response_model=CommissionReadDTO)
async def update_commission(
    cmd: CommissionUpdateCmd,
    use_case: UpdateCommissionUseCaseDep,
    get_use_case: GetCommissionByIdUseCaseDep,
    _permissions=Depends(require_permission("commissions.update")),
    audit_event=Depends(stage_mutation_audit("commission.update", "commission")),
):
    previous = await get_use_case.execute(cmd.id)
    if audit_event and previous:
        audit_event.old_values = previous.model_dump(mode="json")
    entity = await use_case.execute(cmd)
    if audit_event and entity:
        audit_event.entity_id = str(entity.id)
        audit_event.new_values = cmd.model_dump(mode="json")
    if not entity:
        raise HTTPException(status_code=404, detail="Comisión no encontrada")
    return entity


@router.delete("/{commission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_commission(
    commission_id: UUID,
    use_case: DeleteCommissionUseCaseDep,
    get_use_case: GetCommissionByIdUseCaseDep,
    _permissions=Depends(require_permission("commissions.delete")),
    audit_event=Depends(stage_mutation_audit("commission.delete", "commission")),
):
    previous = await get_use_case.execute(commission_id)
    if audit_event:
        audit_event.entity_id = str(commission_id)
        audit_event.old_values = previous.model_dump(mode="json") if previous else None
    await use_case.execute(commission_id)
