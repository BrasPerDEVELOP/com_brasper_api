# app/modules/integraciones/application/use_cases/integration_use_cases.py
"""Casos de uso CRUD para Integration."""
from uuid import UUID
from typing import List, Optional

from app.modules.integraciones.domain.models import Integration
from app.modules.integraciones.interfaces.integration_repository import IntegrationRepositoryInterface
from app.modules.integraciones.application.schemas.integration_schema import (
    IntegrationCreateCmd,
    IntegrationUpdateCmd,
    IntegrationReadDTO,
)


class GetIntegrationByIdUseCase:
    def __init__(self, repo: IntegrationRepositoryInterface):
        self.repo = repo

    async def execute(self, integration_id: UUID) -> Optional[IntegrationReadDTO]:
        entity = await self.repo.get(integration_id)
        if not entity:
            return None
        return IntegrationReadDTO.model_validate(entity)


class ListIntegrationsUseCase:
    def __init__(self, repo: IntegrationRepositoryInterface):
        self.repo = repo

    async def execute(self) -> List[IntegrationReadDTO]:
        items = await self.repo.list()
        return [IntegrationReadDTO.model_validate(x) for x in items]


class CreateIntegrationUseCase:
    def __init__(self, repo: IntegrationRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: IntegrationCreateCmd) -> IntegrationReadDTO:
        entity = Integration(
            name=cmd.name,
            provider=cmd.provider,
            integration_type=cmd.integration_type,
            config=cmd.config,
            description=cmd.description,
        )
        saved = await self.repo.add(entity)
        await self.repo.commit()
        await self.repo.refresh(saved)
        return IntegrationReadDTO.model_validate(saved)


class UpdateIntegrationUseCase:
    def __init__(self, repo: IntegrationRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: IntegrationUpdateCmd) -> Optional[IntegrationReadDTO]:
        entity = await self.repo.get(cmd.id)
        if not entity:
            return None
        if cmd.name is not None:
            entity.name = cmd.name
        if cmd.provider is not None:
            entity.provider = cmd.provider
        if cmd.integration_type is not None:
            entity.integration_type = cmd.integration_type
        if cmd.config is not None:
            entity.config = cmd.config
        if cmd.description is not None:
            entity.description = cmd.description
        await self.repo.update(entity)
        await self.repo.commit()
        await self.repo.refresh(entity)
        return IntegrationReadDTO.model_validate(entity)


class DeleteIntegrationUseCase:
    def __init__(self, repo: IntegrationRepositoryInterface):
        self.repo = repo

    async def execute(self, integration_id: UUID) -> None:
        await self.repo.delete(integration_id)
        await self.repo.commit()
