# app/modules/coin/application/use_cases/tax_rate_use_cases.py
"""Casos de uso CRUD para TaxRate."""
from uuid import UUID
from typing import List, Optional

from app.modules.coin.domain.models import TaxRate
from app.modules.coin.interfaces.tax_rate_repository import TaxRateRepositoryInterface
from app.modules.coin.application.schemas.tax_rate_schema import (
    TaxRateCreateCmd,
    TaxRateUpdateCmd,
    TaxRateReadDTO,
)


class GetTaxRateByIdUseCase:
    def __init__(self, repo: TaxRateRepositoryInterface):
        self.repo = repo

    async def execute(self, tax_rate_id: UUID) -> Optional[TaxRateReadDTO]:
        entity = await self.repo.get(tax_rate_id)
        if not entity:
            return None
        return TaxRateReadDTO.model_validate(entity)


class ListTaxRatesUseCase:
    def __init__(self, repo: TaxRateRepositoryInterface):
        self.repo = repo

    async def execute(self) -> List[TaxRateReadDTO]:
        items = await self.repo.list()
        return [TaxRateReadDTO.model_validate(x) for x in items]


class CreateTaxRateUseCase:
    def __init__(self, repo: TaxRateRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: TaxRateCreateCmd) -> TaxRateReadDTO:
        entity = TaxRate(
            coin_a=cmd.coin_a,
            coin_b=cmd.coin_b,
            tax=cmd.tax,
        )
        saved = await self.repo.add(entity)
        await self.repo.commit()
        await self.repo.refresh(saved)
        return TaxRateReadDTO.model_validate(saved)


class UpdateTaxRateUseCase:
    def __init__(self, repo: TaxRateRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: TaxRateUpdateCmd) -> Optional[TaxRateReadDTO]:
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
        return TaxRateReadDTO.model_validate(entity)


class DeleteTaxRateUseCase:
    def __init__(self, repo: TaxRateRepositoryInterface):
        self.repo = repo

    async def execute(self, tax_rate_id: UUID) -> None:
        await self.repo.delete(tax_rate_id)
        await self.repo.commit()
