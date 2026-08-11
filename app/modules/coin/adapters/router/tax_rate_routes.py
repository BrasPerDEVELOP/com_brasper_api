# app/modules/coin/adapters/router/tax_rate_routes.py
from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from typing import List

from app.modules.coin.application.schemas import (
    TaxRateCreateCmd,
    TaxRateUpdateCmd,
    TaxRateReadDTO,
)
from app.modules.coin.adapters.dependencies import (
    GetTaxRateByIdUseCaseDep,
    ListTaxRatesUseCaseDep,
    CreateTaxRateUseCaseDep,
    UpdateTaxRateUseCaseDep,
    DeleteTaxRateUseCaseDep,
)

from app.core.routing import LegacyAliasRouter
from app.modules.auth.infrastructure.dependencies import require_permission

router = LegacyAliasRouter(prefix="/tax-rate", tags=["tax-rate"])


@router.get("", response_model=List[TaxRateReadDTO])
async def list_tax_rates(use_case: ListTaxRatesUseCaseDep):
    return await use_case.execute()


@router.get("/{tax_rate_id}", response_model=TaxRateReadDTO)
async def get_tax_rate_by_id(
    tax_rate_id: UUID,
    use_case: GetTaxRateByIdUseCaseDep,
    _permissions=Depends(require_permission("rates.view")),
):
    entity = await use_case.execute(tax_rate_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Tasa no encontrada")
    return entity


from app.modules.audit.infrastructure.stage_mutation_audit import stage_mutation_audit


@router.post("", response_model=TaxRateReadDTO, status_code=status.HTTP_201_CREATED)
async def create_tax_rate(
    cmd: TaxRateCreateCmd,
    use_case: CreateTaxRateUseCaseDep,
    _permissions=Depends(require_permission("rates.create")),
    audit_event=Depends(stage_mutation_audit("tax_rate.create", "tax_rate")),
):
    try:
        created = await use_case.execute(cmd)
        if audit_event and created:
            audit_event.entity_id = str(created.id)
            audit_event.new_values = cmd.model_dump(mode="json")
        return created
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("", response_model=TaxRateReadDTO)
async def update_tax_rate(
    cmd: TaxRateUpdateCmd,
    use_case: UpdateTaxRateUseCaseDep,
    get_use_case: GetTaxRateByIdUseCaseDep,
    _permissions=Depends(require_permission("rates.update")),
    audit_event=Depends(stage_mutation_audit("tax_rate.update", "tax_rate")),
):
    previous = await get_use_case.execute(cmd.id)
    if audit_event and previous:
        audit_event.old_values = previous.model_dump(mode="json")
    entity = await use_case.execute(cmd)
    if audit_event and entity:
        audit_event.entity_id = str(entity.id)
        audit_event.new_values = cmd.model_dump(mode="json")
    if not entity:
        raise HTTPException(status_code=404, detail="Tasa no encontrada")
    return entity


@router.delete("/{tax_rate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tax_rate(
    tax_rate_id: UUID,
    use_case: DeleteTaxRateUseCaseDep,
    get_use_case: GetTaxRateByIdUseCaseDep,
    _permissions=Depends(require_permission("rates.delete")),
    audit_event=Depends(stage_mutation_audit("tax_rate.delete", "tax_rate")),
):
    previous = await get_use_case.execute(tax_rate_id)
    if audit_event:
        audit_event.entity_id = str(tax_rate_id)
        audit_event.old_values = previous.model_dump(mode="json") if previous else None
    await use_case.execute(tax_rate_id)
