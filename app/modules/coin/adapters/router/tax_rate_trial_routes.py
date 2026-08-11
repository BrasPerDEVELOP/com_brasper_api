# app/modules/coin/adapters/router/tax_rate_trial_routes.py
from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from typing import List

from app.modules.coin.application.schemas import (
    TaxRateTrialCreateCmd,
    TaxRateTrialUpdateCmd,
    TaxRateTrialReadDTO,
)
from app.modules.coin.adapters.dependencies import (
    GetTaxRateTrialByIdUseCaseDep,
    ListTaxRateTrialsUseCaseDep,
    CreateTaxRateTrialUseCaseDep,
    UpdateTaxRateTrialUseCaseDep,
    DeleteTaxRateTrialUseCaseDep,
)

from app.core.routing import LegacyAliasRouter
from app.modules.auth.infrastructure.dependencies import require_permission

router = LegacyAliasRouter(prefix="/tax-rate-trial", tags=["tax-rate-trial"])


@router.get("", response_model=List[TaxRateTrialReadDTO])
async def list_tax_rate_trials(
    use_case: ListTaxRateTrialsUseCaseDep,
    _permissions=Depends(require_permission("rates.view")),
):
    return await use_case.execute()


@router.get("/{tax_rate_trial_id}", response_model=TaxRateTrialReadDTO)
async def get_tax_rate_trial_by_id(
    tax_rate_trial_id: UUID,
    use_case: GetTaxRateTrialByIdUseCaseDep,
    _permissions=Depends(require_permission("rates.view")),
):
    entity = await use_case.execute(tax_rate_trial_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Tasa prueba no encontrada")
    return entity


from app.modules.audit.infrastructure.stage_mutation_audit import stage_mutation_audit


@router.post("", response_model=TaxRateTrialReadDTO, status_code=status.HTTP_201_CREATED)
async def create_tax_rate_trial(
    cmd: TaxRateTrialCreateCmd,
    use_case: CreateTaxRateTrialUseCaseDep,
    _permissions=Depends(require_permission("rates.create")),
    audit_event=Depends(stage_mutation_audit("tax_rate_trial.create", "tax_rate_trial")),
):
    try:
        created = await use_case.execute(cmd)
        if audit_event and created:
            audit_event.entity_id = str(created.id)
            audit_event.new_values = cmd.model_dump(mode="json")
        return created
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("", response_model=TaxRateTrialReadDTO)
async def update_tax_rate_trial(
    cmd: TaxRateTrialUpdateCmd,
    use_case: UpdateTaxRateTrialUseCaseDep,
    get_use_case: GetTaxRateTrialByIdUseCaseDep,
    _permissions=Depends(require_permission("rates.update")),
    audit_event=Depends(stage_mutation_audit("tax_rate_trial.update", "tax_rate_trial")),
):
    previous = await get_use_case.execute(cmd.id)
    if audit_event and previous:
        audit_event.old_values = previous.model_dump(mode="json")
    entity = await use_case.execute(cmd)
    if audit_event and entity:
        audit_event.entity_id = str(entity.id)
        audit_event.new_values = cmd.model_dump(mode="json")
    if not entity:
        raise HTTPException(status_code=404, detail="Tasa prueba no encontrada")
    return entity


@router.delete("/{tax_rate_trial_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tax_rate_trial(
    tax_rate_trial_id: UUID,
    use_case: DeleteTaxRateTrialUseCaseDep,
    get_use_case: GetTaxRateTrialByIdUseCaseDep,
    _permissions=Depends(require_permission("rates.delete")),
    audit_event=Depends(stage_mutation_audit("tax_rate_trial.delete", "tax_rate_trial")),
):
    previous = await get_use_case.execute(tax_rate_trial_id)
    if audit_event:
        audit_event.entity_id = str(tax_rate_trial_id)
        audit_event.old_values = previous.model_dump(mode="json") if previous else None
    await use_case.execute(tax_rate_trial_id)
