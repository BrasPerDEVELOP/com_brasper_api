"""Casos de uso CRUD y listado agrupado para Bank."""
from uuid import UUID
from typing import List, Optional

from app.modules.transactions.domain.models import Bank
from app.modules.transactions.interfaces.bank_repository import BankRepositoryInterface
from app.modules.transactions.application.schemas.bank_schema import (
    BankCreateCmd,
    BankUpdateCmd,
    BankReadDTO,
    BankItemDTO,
    BanksByCountryCurrencyDTO,
    CURRENCY_DISPLAY_BANK,
)
from app.modules.transactions.domain.enums import BankCountry


def _to_item_dto(entity: Bank) -> BankItemDTO:
    return BankItemDTO(
        bank=entity.bank,
        account=entity.account,
        pix=entity.pix,
        company=entity.company,
        currency=CURRENCY_DISPLAY_BANK.get(entity.currency.value, entity.currency.value.upper()),
        image=entity.image,
    )


class GetBankByIdUseCase:
    def __init__(self, repo: BankRepositoryInterface):
        self.repo = repo

    async def execute(self, bank_id: UUID) -> Optional[BankReadDTO]:
        entity = await self.repo.get(bank_id)
        if not entity:
            return None
        return BankReadDTO.from_bank(entity)


class ListBanksUseCase:
    def __init__(self, repo: BankRepositoryInterface):
        self.repo = repo

    async def execute(self) -> List[BankReadDTO]:
        items = await self.repo.list()
        return [BankReadDTO.from_bank(x) for x in items]


class ListBanksByCountryCurrencyUseCase:
    """Devuelve bancos agrupados por país (PE, BR) y luego por moneda (PEN, USD, BRL)."""
    def __init__(self, repo: BankRepositoryInterface):
        self.repo = repo

    async def execute(self) -> BanksByCountryCurrencyDTO:
        items = await self.repo.list()
        pe: dict[str, list[BankItemDTO]] = {}
        br: dict[str, list[BankItemDTO]] = {}
        for entity in items:
            item = _to_item_dto(entity)
            key = entity.currency.value.upper()
            if entity.country == BankCountry.pe:
                pe.setdefault(key, []).append(item)
            else:
                br.setdefault(key, []).append(item)
        return BanksByCountryCurrencyDTO(pe=pe if pe else None, br=br if br else None)


class CreateBankUseCase:
    def __init__(self, repo: BankRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: BankCreateCmd) -> BankReadDTO:
        entity = Bank(
            bank=cmd.bank,
            account=cmd.account,
            pix=cmd.pix,
            company=cmd.company,
            currency=cmd.currency,
            image=cmd.image,
            country=cmd.country,
        )
        saved = await self.repo.add(entity)
        await self.repo.commit()
        await self.repo.refresh(saved)
        return BankReadDTO.from_bank(saved)


class UpdateBankUseCase:
    def __init__(self, repo: BankRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: BankUpdateCmd) -> Optional[BankReadDTO]:
        entity = await self.repo.get(cmd.id)
        if not entity:
            return None
        if cmd.bank is not None:
            entity.bank = cmd.bank
        if cmd.account is not None:
            entity.account = cmd.account
        if cmd.pix is not None:
            entity.pix = cmd.pix
        if cmd.company is not None:
            entity.company = cmd.company
        if cmd.currency is not None:
            entity.currency = cmd.currency
        if cmd.image is not None:
            entity.image = cmd.image
        if cmd.country is not None:
            entity.country = cmd.country
        await self.repo.update(entity)
        await self.repo.commit()
        await self.repo.refresh(entity)
        return BankReadDTO.from_bank(entity)


class DeleteBankUseCase:
    def __init__(self, repo: BankRepositoryInterface):
        self.repo = repo

    async def execute(self, bank_id: UUID) -> None:
        await self.repo.delete(bank_id)
        await self.repo.commit()
