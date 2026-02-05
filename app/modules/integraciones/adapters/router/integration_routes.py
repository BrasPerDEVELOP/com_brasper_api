# app/modules/integraciones/adapters/router/integration_routes.py
from fastapi import APIRouter, HTTPException, status
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

router = APIRouter(prefix="/integration", tags=["integration"])


@router.get("", response_model=List[IntegrationReadDTO])
async def list_integrations(use_case: ListIntegrationsUseCaseDep):
    return await use_case.execute()


@router.get("/{integration_id}", response_model=IntegrationReadDTO)
async def get_integration_by_id(integration_id: UUID, use_case: GetIntegrationByIdUseCaseDep):
    entity = await use_case.execute(integration_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Integración no encontrada")
    return entity


@router.post("", response_model=IntegrationReadDTO, status_code=status.HTTP_201_CREATED)
async def create_integration(cmd: IntegrationCreateCmd, use_case: CreateIntegrationUseCaseDep):
    try:
        return await use_case.execute(cmd)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("", response_model=IntegrationReadDTO)
async def update_integration(cmd: IntegrationUpdateCmd, use_case: UpdateIntegrationUseCaseDep):
    entity = await use_case.execute(cmd)
    if not entity:
        raise HTTPException(status_code=404, detail="Integración no encontrada")
    return entity


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_integration(integration_id: UUID, use_case: DeleteIntegrationUseCaseDep):
    await use_case.execute(integration_id)
