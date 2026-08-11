# app/modules/integraciones/adapters/router/integration_routes.py
from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from typing import List

from app.modules.integraciones.application.schemas import (
    IntegrationCreateCmd,
    IntegrationUpdateCmd,
    IntegrationReadDTO,
)
from app.modules.integraciones.adapters.dependencies import (
    GetIntegrationByIdUseCaseDep,
    ListIntegrationsUseCaseDep,
    CreateIntegrationUseCaseDep,
    UpdateIntegrationUseCaseDep,
    DeleteIntegrationUseCaseDep,
)

from app.core.routing import LegacyAliasRouter
from app.modules.auth.infrastructure.dependencies import require_permission

router = LegacyAliasRouter(prefix="/integration", tags=["integration"])


@router.get("", response_model=List[IntegrationReadDTO])
async def list_integrations(
    use_case: ListIntegrationsUseCaseDep,
    _permissions=Depends(require_permission("integrations.view")),
):
    return await use_case.execute()


@router.get("/{integration_id}", response_model=IntegrationReadDTO)
async def get_integration_by_id(
    integration_id: UUID,
    use_case: GetIntegrationByIdUseCaseDep,
    _permissions=Depends(require_permission("integrations.view")),
):
    entity = await use_case.execute(integration_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Integración no encontrada")
    return entity


from app.modules.audit.infrastructure.stage_mutation_audit import stage_mutation_audit


@router.post("", response_model=IntegrationReadDTO, status_code=status.HTTP_201_CREATED)
async def create_integration(
    cmd: IntegrationCreateCmd,
    use_case: CreateIntegrationUseCaseDep,
    _permissions=Depends(require_permission("integrations.create")),
    audit_event=Depends(stage_mutation_audit("integration.create", "integration")),
):
    try:
        created = await use_case.execute(cmd)
        if audit_event and created:
            audit_event.entity_id = str(created.id)
            audit_event.new_values = cmd.model_dump(mode="json")
        return created
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("", response_model=IntegrationReadDTO)
async def update_integration(
    cmd: IntegrationUpdateCmd,
    use_case: UpdateIntegrationUseCaseDep,
    get_use_case: GetIntegrationByIdUseCaseDep,
    _permissions=Depends(require_permission("integrations.update")),
    audit_event=Depends(stage_mutation_audit("integration.update", "integration")),
):
    previous = await get_use_case.execute(cmd.id)
    if audit_event and previous:
        audit_event.old_values = previous.model_dump(mode="json")
    entity = await use_case.execute(cmd)
    if audit_event and entity:
        audit_event.entity_id = str(entity.id)
        audit_event.new_values = cmd.model_dump(mode="json")
    if not entity:
        raise HTTPException(status_code=404, detail="Integración no encontrada")
    return entity


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_integration(
    integration_id: UUID,
    use_case: DeleteIntegrationUseCaseDep,
    get_use_case: GetIntegrationByIdUseCaseDep,
    _permissions=Depends(require_permission("integrations.delete")),
    audit_event=Depends(stage_mutation_audit("integration.delete", "integration")),
):
    previous = await get_use_case.execute(integration_id)
    if audit_event:
        audit_event.entity_id = str(integration_id)
        audit_event.old_values = previous.model_dump(mode="json") if previous else None
    await use_case.execute(integration_id)
