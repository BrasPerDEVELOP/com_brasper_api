"""Casos de uso CRUD para TaxRateTrial (tasa prueba)."""
from uuid import UUID
from typing import List, Optional

from app.modules.coin.domain.models import TaxRateTrial
from app.modules.coin.interfaces.tax_rate_trial_repository import TaxRateTrialRepositoryInterface
from app.modules.coin.application.schemas.tax_rate_trial_schema import (
    TaxRateTrialCreateCmd,
    TaxRateTrialUpdateCmd,
    TaxRateTrialReadDTO,
)


class GetTaxRateTrialByIdUseCase:
    def __init__(self, repo: TaxRateTrialRepositoryInterface):
        self.repo = repo

    async def execute(self, tax_rate_trial_id: UUID) -> Optional[TaxRateTrialReadDTO]:
        entity = await self.repo.get(tax_rate_trial_id)
        if not entity:
            return None
        return TaxRateTrialReadDTO.model_validate(entity)


class ListTaxRateTrialsUseCase:
    def __init__(self, repo: TaxRateTrialRepositoryInterface):
        self.repo = repo

    async def execute(self) -> List[TaxRateTrialReadDTO]:
        items = await self.repo.list()
        return [TaxRateTrialReadDTO.model_validate(x) for x in items]


class CreateTaxRateTrialUseCase:
    def __init__(self, repo: TaxRateTrialRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: TaxRateTrialCreateCmd) -> TaxRateTrialReadDTO:
        entity = TaxRateTrial(
            coin_a=cmd.coin_a,
            coin_b=cmd.coin_b,
            tax=cmd.tax,
        )
        saved = await self.repo.add(entity)
        await self.repo.commit()
        await self.repo.refresh(saved)
        return TaxRateTrialReadDTO.model_validate(saved)


class UpdateTaxRateTrialUseCase:
    def __init__(self, repo: TaxRateTrialRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: TaxRateTrialUpdateCmd) -> Optional[TaxRateTrialReadDTO]:
        entity = await self.repo.get(cmd.id)
        if not entity:
            return None
        if cmd.coin_a is not None:
            entity.coin_a = cmd.coin_a
        if cmd.coin_b is not None:
            entity.coin_b = cmd.coin_b
        if cmd.tax is not None:
            entity.tax = cmd.tax
        await self.repo.update(entity)
        await self.repo.commit()
        await self.repo.refresh(entity)
        return TaxRateTrialReadDTO.model_validate(entity)


class DeleteTaxRateTrialUseCase:
    def __init__(self, repo: TaxRateTrialRepositoryInterface):
        self.repo = repo

    async def execute(self, tax_rate_trial_id: UUID) -> None:
        await self.repo.delete(tax_rate_trial_id)
        await self.repo.commit()
