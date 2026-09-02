# app/modules/coin/adapters/router/commission_accounting_routes.py
from fastapi import Depends, HTTPException, status
from uuid import UUID
from typing import List

from app.modules.coin.application.schemas import (
    CommissionAccountingCreateCmd,
    CommissionAccountingUpdateCmd,
    CommissionAccountingReadDTO,
    CommissionAccountingSettingsUpsertCmd,
    CommissionAccountingSettingsReadDTO,
)
from app.modules.coin.adapters.dependencies import (
    GetCommissionAccountingByIdUseCaseDep,
    ListCommissionAccountingsUseCaseDep,
    CreateCommissionAccountingUseCaseDep,
    UpdateCommissionAccountingUseCaseDep,
    DeleteCommissionAccountingUseCaseDep,
    GetCommissionAccountingSettingsUseCaseDep,
    UpsertCommissionAccountingSettingsUseCaseDep,
)

from app.core.routing import LegacyAliasRouter
from app.modules.auth.infrastructure.dependencies import require_permission
from app.modules.audit.infrastructure.stage_mutation_audit import stage_mutation_audit

router = LegacyAliasRouter(prefix="/commission-accounting", tags=["commission-accounting"])


@router.get("", response_model=List[CommissionAccountingReadDTO])
async def list_commission_accountings(
    use_case: ListCommissionAccountingsUseCaseDep,
    _permissions=Depends(require_permission("commissions.view")),
):
    return await use_case.execute()


# `/settings` debe ir ANTES de `/{id}`: si no, FastAPI interpreta "settings" como UUID → 422.
@router.get("/settings", response_model=CommissionAccountingSettingsReadDTO)
@router.get("/settings/", response_model=CommissionAccountingSettingsReadDTO)
async def get_commission_accounting_settings(
    use_case: GetCommissionAccountingSettingsUseCaseDep,
    _permissions=Depends(require_permission("commissions.view")),
):
    return await use_case.execute()


@router.put("/settings", response_model=CommissionAccountingSettingsReadDTO)
@router.put("/settings/", response_model=CommissionAccountingSettingsReadDTO)
async def upsert_commission_accounting_settings(
    cmd: CommissionAccountingSettingsUpsertCmd,
    use_case: UpsertCommissionAccountingSettingsUseCaseDep,
    _permissions=Depends(require_permission("commissions.update")),
    audit_event=Depends(
        stage_mutation_audit("commission_accounting.settings_upsert", "commission_accounting_settings")
    ),
):
    updated = await use_case.execute(cmd)
    if audit_event:
        audit_event.new_values = cmd.model_dump(mode="json")
    return updated


@router.get("/{commission_accounting_id}", response_model=CommissionAccountingReadDTO)
async def get_commission_accounting_by_id(
    commission_accounting_id: UUID,
    use_case: GetCommissionAccountingByIdUseCaseDep,
    _permissions=Depends(require_permission("commissions.view")),
):
    entity = await use_case.execute(commission_accounting_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Comisión contable no encontrada")
    return entity


@router.post("", response_model=CommissionAccountingReadDTO, status_code=status.HTTP_201_CREATED)
async def create_commission_accounting(
    cmd: CommissionAccountingCreateCmd,
    use_case: CreateCommissionAccountingUseCaseDep,
    _permissions=Depends(require_permission("commissions.create")),
    audit_event=Depends(stage_mutation_audit("commission_accounting.create", "commission_accounting")),
):
    try:
        created = await use_case.execute(cmd)
        if audit_event and created:
            audit_event.entity_id = str(created.id)
            audit_event.new_values = cmd.model_dump(mode="json")
        return created
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("", response_model=CommissionAccountingReadDTO)
async def update_commission_accounting(
    cmd: CommissionAccountingUpdateCmd,
    use_case: UpdateCommissionAccountingUseCaseDep,
    get_use_case: GetCommissionAccountingByIdUseCaseDep,
    _permissions=Depends(require_permission("commissions.update")),
    audit_event=Depends(stage_mutation_audit("commission_accounting.update", "commission_accounting")),
):
    previous = await get_use_case.execute(cmd.id)
    if audit_event and previous:
        audit_event.old_values = previous.model_dump(mode="json")
    entity = await use_case.execute(cmd)
    if audit_event and entity:
        audit_event.entity_id = str(entity.id)
        audit_event.new_values = cmd.model_dump(mode="json")
    if not entity:
        raise HTTPException(status_code=404, detail="Comisión contable no encontrada")
    return entity


@router.delete("/{commission_accounting_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_commission_accounting(
    commission_accounting_id: UUID,
    use_case: DeleteCommissionAccountingUseCaseDep,
    get_use_case: GetCommissionAccountingByIdUseCaseDep,
    _permissions=Depends(require_permission("commissions.delete")),
    audit_event=Depends(stage_mutation_audit("commission_accounting.delete", "commission_accounting")),
):
    previous = await get_use_case.execute(commission_accounting_id)
    if audit_event:
        audit_event.entity_id = str(commission_accounting_id)
        audit_event.old_values = previous.model_dump(mode="json") if previous else None
    await use_case.execute(commission_accounting_id)
