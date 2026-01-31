"""Casos de uso CRUD para BankAccount."""
from uuid import UUID
from typing import List, Optional

from app.modules.transactions.domain.models import BankAccount
from app.modules.transactions.interfaces.bank_account_repository import BankAccountRepositoryInterface
from app.modules.transactions.application.schemas.bank_account_schema import (
    BankAccountCreateCmd,
    BankAccountUpdateCmd,
    BankAccountReadDTO,
)


class GetBankAccountByIdUseCase:
    def __init__(self, repo: BankAccountRepositoryInterface):
        self.repo = repo

    async def execute(self, bank_account_id: UUID) -> Optional[BankAccountReadDTO]:
        entity = await self.repo.get(bank_account_id)
        if not entity:
            return None
        return BankAccountReadDTO.model_validate(entity)


class ListBankAccountsUseCase:
    def __init__(self, repo: BankAccountRepositoryInterface):
        self.repo = repo

    async def execute(self) -> List[BankAccountReadDTO]:
        items = await self.repo.list()
        return [BankAccountReadDTO.model_validate(x) for x in items]


class CreateBankAccountUseCase:
    def __init__(self, repo: BankAccountRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: BankAccountCreateCmd) -> BankAccountReadDTO:
        entity = BankAccount(
            user_id=cmd.user_id,
            bank_id=cmd.bank_id,
            account_flow=cmd.account_flow,
            account_holder_type=cmd.account_holder_type,
            bank_country=cmd.bank_country,
            holder_names=cmd.holder_names,
            holder_surnames=cmd.holder_surnames,
            document_number=cmd.document_number,
            business_name=cmd.business_name,
            ruc_number=cmd.ruc_number,
            legal_representative_name=cmd.legal_representative_name,
            legal_representative_document=cmd.legal_representative_document,
            account_number=cmd.account_number,
            account_number_confirmation=cmd.account_number_confirmation,
            cci_number=cmd.cci_number,
            cci_number_confirmation=cmd.cci_number_confirmation,
            pix_key=cmd.pix_key,
            pix_key_confirmation=cmd.pix_key_confirmation,
            pix_key_type=cmd.pix_key_type,
            cpf=cmd.cpf,
        )
        saved = await self.repo.add(entity)
        await self.repo.commit()
        await self.repo.refresh(saved)
        return BankAccountReadDTO.model_validate(saved)


class UpdateBankAccountUseCase:
    def __init__(self, repo: BankAccountRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: BankAccountUpdateCmd) -> Optional[BankAccountReadDTO]:
        entity = await self.repo.get(cmd.id)
        if not entity:
            return None
        if cmd.user_id is not None:
            entity.user_id = cmd.user_id
        if cmd.bank_id is not None:
            entity.bank_id = cmd.bank_id
        if cmd.account_flow is not None:
            entity.account_flow = cmd.account_flow
        if cmd.account_holder_type is not None:
            entity.account_holder_type = cmd.account_holder_type
        if cmd.bank_country is not None:
            entity.bank_country = cmd.bank_country
        if cmd.holder_names is not None:
            entity.holder_names = cmd.holder_names
        if cmd.holder_surnames is not None:
            entity.holder_surnames = cmd.holder_surnames
        if cmd.document_number is not None:
            entity.document_number = cmd.document_number
        if cmd.business_name is not None:
            entity.business_name = cmd.business_name
        if cmd.ruc_number is not None:
            entity.ruc_number = cmd.ruc_number
        if cmd.legal_representative_name is not None:
            entity.legal_representative_name = cmd.legal_representative_name
        if cmd.legal_representative_document is not None:
            entity.legal_representative_document = cmd.legal_representative_document
        if cmd.account_number is not None:
            entity.account_number = cmd.account_number
        if cmd.account_number_confirmation is not None:
            entity.account_number_confirmation = cmd.account_number_confirmation
        if cmd.cci_number is not None:
            entity.cci_number = cmd.cci_number
        if cmd.cci_number_confirmation is not None:
            entity.cci_number_confirmation = cmd.cci_number_confirmation
        if cmd.pix_key is not None:
            entity.pix_key = cmd.pix_key
        if cmd.pix_key_confirmation is not None:
            entity.pix_key_confirmation = cmd.pix_key_confirmation
        if cmd.pix_key_type is not None:
            entity.pix_key_type = cmd.pix_key_type
        if cmd.cpf is not None:
            entity.cpf = cmd.cpf
        await self.repo.update(entity)
        await self.repo.commit()
        await self.repo.refresh(entity)
        return BankAccountReadDTO.model_validate(entity)


class DeleteBankAccountUseCase:
    def __init__(self, repo: BankAccountRepositoryInterface):
        self.repo = repo

    async def execute(self, bank_account_id: UUID) -> None:
        await self.repo.delete(bank_account_id)
        await self.repo.commit()
