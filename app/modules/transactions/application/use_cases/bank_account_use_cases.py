"""Casos de uso CRUD para BankAccount."""
from uuid import UUID
from typing import List, Optional

from app.modules.transactions.domain.models import BankAccount
from app.shared.query_filter import FilterSchema, OperatorEnum, QueryFilter
from app.modules.transactions.interfaces.bank_account_repository import BankAccountRepositoryInterface
from app.modules.transactions.interfaces.bank_repository import BankRepositoryInterface
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

    async def execute(self, user_id: Optional[UUID] = None) -> List[BankAccountReadDTO]:
        query_filter = None
        if user_id:
            query_filter = QueryFilter(
                filters=[FilterSchema(field="user_id", value=user_id, operator=OperatorEnum.EQ)]
            )
        items = await self.repo.list(query_filter=query_filter)
        return [BankAccountReadDTO.model_validate(x) for x in items]


class CreateBankAccountUseCase:
    def __init__(
        self,
        repo: BankAccountRepositoryInterface,
        bank_repo: BankRepositoryInterface,
    ):
        self.repo = repo
        self.bank_repo = bank_repo

    async def execute(self, cmd: BankAccountCreateCmd) -> BankAccountReadDTO:
        bank = await self.bank_repo.get(cmd.bank_id)
        if not bank:
            raise ValueError(f"Banco con id {cmd.bank_id} no existe")
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
            cci_number=cmd.cci_number,
            pix_key=cmd.pix_key,
            pix_key_type=cmd.pix_key_type,
            cpf=cmd.cpf,
        )
        saved = await self.repo.add(entity)
        await self.repo.commit()
        await self.repo.refresh(saved)
        return BankAccountReadDTO.model_validate(saved)


class UpdateBankAccountUseCase:
    def __init__(
        self,
        repo: BankAccountRepositoryInterface,
        bank_repo: BankRepositoryInterface,
    ):
        self.repo = repo
        self.bank_repo = bank_repo

    async def execute(self, cmd: BankAccountUpdateCmd) -> Optional[BankAccountReadDTO]:
        entity = await self.repo.get(cmd.id)
        if not entity:
            return None
        if cmd.bank_id is not None:
            bank = await self.bank_repo.get(cmd.bank_id)
            if not bank:
                raise ValueError(f"Banco con id {cmd.bank_id} no existe")
        if cmd.user_id is not None:
            entity.user_id = cmd.user_id
        if cmd.bank_id is not None:
            entity.bank_id = cmd.bank_id  # ya validado arriba
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
        if cmd.cci_number is not None:
            entity.cci_number = cmd.cci_number
        if cmd.pix_key is not None:
            entity.pix_key = cmd.pix_key
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

    async def execute(self, bank_account_id: UUID) -> bool:
        """Soft-delete. Retorna False si la cuenta no existe (o ya estaba eliminada)."""
        result = await self.repo.delete(bank_account_id)
        await self.repo.commit()
        return bool(result.get("status")) if isinstance(result, dict) else bool(result)
