# app/modules/coin/application/use_cases/commission_accounting_use_cases.py
"""Casos de uso CRUD para CommissionAccounting."""
from uuid import UUID
from typing import List, Optional

from app.modules.coin.domain.models import CommissionAccounting
from app.modules.coin.interfaces.commission_accounting_repository import (
    CommissionAccountingRepositoryInterface,
)
from app.modules.coin.application.schemas.commission_accounting_schema import (
    CommissionAccountingCreateCmd,
    CommissionAccountingUpdateCmd,
    CommissionAccountingReadDTO,
)


class GetCommissionAccountingByIdUseCase:
    def __init__(self, repo: CommissionAccountingRepositoryInterface):
        self.repo = repo

    async def execute(self, commission_accounting_id: UUID) -> Optional[CommissionAccountingReadDTO]:
        entity = await self.repo.get(commission_accounting_id)
        if not entity:
            return None
        return CommissionAccountingReadDTO.model_validate(entity)


class ListCommissionAccountingsUseCase:
    def __init__(self, repo: CommissionAccountingRepositoryInterface):
        self.repo = repo

    async def execute(self) -> List[CommissionAccountingReadDTO]:
        items = await self.repo.list()
        return [CommissionAccountingReadDTO.model_validate(x) for x in items]


class CreateCommissionAccountingUseCase:
    def __init__(self, repo: CommissionAccountingRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: CommissionAccountingCreateCmd) -> CommissionAccountingReadDTO:
        entity = CommissionAccounting(
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
        return CommissionAccountingReadDTO.model_validate(saved)


class UpdateCommissionAccountingUseCase:
    def __init__(self, repo: CommissionAccountingRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: CommissionAccountingUpdateCmd) -> Optional[CommissionAccountingReadDTO]:
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
        return CommissionAccountingReadDTO.model_validate(entity)


class DeleteCommissionAccountingUseCase:
    def __init__(self, repo: CommissionAccountingRepositoryInterface):
        self.repo = repo

    async def execute(self, commission_accounting_id: UUID) -> None:
        await self.repo.delete(commission_accounting_id)
        await self.repo.commit()
