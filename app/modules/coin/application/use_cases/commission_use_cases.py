# app/modules/coin/application/use_cases/commission_use_cases.py
"""Casos de uso CRUD para Commission."""
from uuid import UUID
from typing import List, Optional

from app.modules.coin.domain.models import Commission
from app.modules.coin.interfaces.commission_repository import CommissionRepositoryInterface
from app.modules.coin.application.schemas.commission_schema import (
    CommissionCreateCmd,
    CommissionUpdateCmd,
    CommissionReadDTO,
)


class GetCommissionByIdUseCase:
    def __init__(self, repo: CommissionRepositoryInterface):
        self.repo = repo

    async def execute(self, commission_id: UUID) -> Optional[CommissionReadDTO]:
        entity = await self.repo.get(commission_id)
        if not entity:
            return None
        return CommissionReadDTO.model_validate(entity)


class ListCommissionsUseCase:
    def __init__(self, repo: CommissionRepositoryInterface):
        self.repo = repo

    async def execute(self) -> List[CommissionReadDTO]:
        items = await self.repo.list()
        return [CommissionReadDTO.model_validate(x) for x in items]


class CreateCommissionUseCase:
    def __init__(self, repo: CommissionRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: CommissionCreateCmd) -> CommissionReadDTO:
        entity = Commission(
            coin_a=cmd.coin_a,
            coin_b=cmd.coin_b,
            percentage=cmd.percentage,
            reverse=cmd.reverse,
            min_amount=cmd.min_amount,
            max_amount=cmd.max_amount,
        )
        saved = await self.repo.add(entity)
        await self.repo.commit()
        await self.repo.refresh(saved)
        return CommissionReadDTO.model_validate(saved)


class UpdateCommissionUseCase:
    def __init__(self, repo: CommissionRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: CommissionUpdateCmd) -> Optional[CommissionReadDTO]:
        entity = await self.repo.get(cmd.id)
        if not entity:
            return None
        if cmd.coin_a is not None:
            entity.coin_a = cmd.coin_a
        if cmd.coin_b is not None:
            entity.coin_b = cmd.coin_b
        if cmd.percentage is not None:
            entity.percentage = cmd.percentage
        if cmd.reverse is not None:
            entity.reverse = cmd.reverse
        if cmd.min_amount is not None:
            entity.min_amount = cmd.min_amount
        if cmd.max_amount is not None:
            entity.max_amount = cmd.max_amount
        await self.repo.update(entity)
        await self.repo.commit()
        await self.repo.refresh(entity)
        return CommissionReadDTO.model_validate(entity)


class DeleteCommissionUseCase:
    def __init__(self, repo: CommissionRepositoryInterface):
        self.repo = repo

    async def execute(self, commission_id: UUID) -> None:
        await self.repo.delete(commission_id)
        await self.repo.commit()
