from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from typing import List

from app.modules.coin.application.schemas import (
    CommissionTrialCreateCmd,
    CommissionTrialUpdateCmd,
    CommissionTrialReadDTO,
)
from app.modules.coin.adapters.dependencies import (
    GetCommissionTrialByIdUseCaseDep,
    ListCommissionTrialsUseCaseDep,
    CreateCommissionTrialUseCaseDep,
    UpdateCommissionTrialUseCaseDep,
    DeleteCommissionTrialUseCaseDep,
)

from app.core.routing import LegacyAliasRouter
from app.modules.auth.infrastructure.dependencies import require_permission

router = LegacyAliasRouter(prefix="/commission-trial", tags=["commission-trial"])


@router.get("", response_model=List[CommissionTrialReadDTO])
async def list_commission_trials(
    use_case: ListCommissionTrialsUseCaseDep,
    _permissions=Depends(require_permission("commissions.view")),
):
    return await use_case.execute()


@router.get("/{commission_trial_id}", response_model=CommissionTrialReadDTO)
async def get_commission_trial_by_id(
    commission_trial_id: UUID,
    use_case: GetCommissionTrialByIdUseCaseDep,
    _permissions=Depends(require_permission("commissions.view")),
):
    entity = await use_case.execute(commission_trial_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Comisión prueba no encontrada")
    return entity


from app.modules.audit.infrastructure.stage_mutation_audit import stage_mutation_audit


@router.post("", response_model=CommissionTrialReadDTO, status_code=status.HTTP_201_CREATED)
async def create_commission_trial(
    cmd: CommissionTrialCreateCmd,
    use_case: CreateCommissionTrialUseCaseDep,
    _permissions=Depends(require_permission("commissions.create")),
    audit_event=Depends(stage_mutation_audit("commission_trial.create", "commission_trial")),
):
    try:
        created = await use_case.execute(cmd)
        if audit_event and created:
            audit_event.entity_id = str(created.id)
            audit_event.new_values = cmd.model_dump(mode="json")
        return created
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("", response_model=CommissionTrialReadDTO)
async def update_commission_trial(
    cmd: CommissionTrialUpdateCmd,
    use_case: UpdateCommissionTrialUseCaseDep,
    get_use_case: GetCommissionTrialByIdUseCaseDep,
    _permissions=Depends(require_permission("commissions.update")),
    audit_event=Depends(stage_mutation_audit("commission_trial.update", "commission_trial")),
):
    previous = await get_use_case.execute(cmd.id)
    if audit_event and previous:
        audit_event.old_values = previous.model_dump(mode="json")
    entity = await use_case.execute(cmd)
    if audit_event and entity:
        audit_event.entity_id = str(entity.id)
        audit_event.new_values = cmd.model_dump(mode="json")
    if not entity:
        raise HTTPException(status_code=404, detail="Comisión prueba no encontrada")
    return entity


@router.delete("/{commission_trial_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_commission_trial(
    commission_trial_id: UUID,
    use_case: DeleteCommissionTrialUseCaseDep,
    get_use_case: GetCommissionTrialByIdUseCaseDep,
    _permissions=Depends(require_permission("commissions.delete")),
    audit_event=Depends(stage_mutation_audit("commission_trial.delete", "commission_trial")),
):
    previous = await get_use_case.execute(commission_trial_id)
    if audit_event:
        audit_event.entity_id = str(commission_trial_id)
        audit_event.old_values = previous.model_dump(mode="json") if previous else None
    await use_case.execute(commission_trial_id)
