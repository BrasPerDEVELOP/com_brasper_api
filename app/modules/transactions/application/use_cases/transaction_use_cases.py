# app/modules/transactions/application/use_cases/transaction_use_cases.py
"""Casos de uso CRUD para Transaction."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.users.application.use_cases import CreateUserUseCase
    from app.modules.transactions.application.use_cases.bank_account_use_cases import CreateBankAccountUseCase

from app.shared.query_filter import FilterSchema, OperatorEnum, QueryFilter
from app.modules.transactions.domain.models import Transaction
from app.modules.transactions.domain.enums import TransactionStatus
from app.modules.transactions.interfaces.transaction_repository import TransactionRepositoryInterface
from app.modules.transactions.application.schemas.transaction_schema import (
    TransactionCreateCmd,
    TransactionUpdateCmd,
    TransactionReadDTO,
    ImportRequestCmd,
    ImportResponseDTO,
)

# Mapeo cmd -> entity (campos con sufijo _id en el modelo)
_CMD_TO_ENTITY = {
    "bank_account_origin": "bank_account_origin_id",
    "bank_account_destination": "bank_account_destination_id",
}


def _build_transaction_query_filter(
    status: Optional[TransactionStatus] = None,
    user_id: Optional[UUID] = None,
    bank_account_origin_id: Optional[UUID] = None,
    bank_account_destination_id: Optional[UUID] = None,
    created_at_from: Optional[datetime] = None,
    created_at_to: Optional[datetime] = None,
) -> Optional[QueryFilter]:
    """Construye QueryFilter para transacciones."""
    filter_specs = [
        (status, "status", OperatorEnum.EQ),
        (user_id, "user_id", OperatorEnum.EQ),
        (bank_account_origin_id, "bank_account_origin_id", OperatorEnum.EQ),
        (bank_account_destination_id, "bank_account_destination_id", OperatorEnum.EQ),
        (created_at_from, "created_at", OperatorEnum.GTE),
        (created_at_to, "created_at", OperatorEnum.LTE),
    ]
    filters = [
        FilterSchema(field=field, value=val, operator=op)
        for val, field, op in filter_specs
        if val is not None
    ]
    return QueryFilter(filters=filters) if filters else None


def _cmd_to_entity_data(data: dict) -> dict:
    """Convierte nombres de campos del cmd al modelo entity."""
    return {
        _CMD_TO_ENTITY.get(k, k): v
        for k, v in data.items()
        if k != "id"
    }


class GetTransactionByIdUseCase:
    def __init__(self, repo: TransactionRepositoryInterface):
        self.repo = repo

    async def execute(self, transaction_id: UUID) -> Optional[TransactionReadDTO]:
        entity = await self.repo.get(transaction_id)
        return TransactionReadDTO.model_validate(entity) if entity else None


class ListTransactionsUseCase:
    def __init__(self, repo: TransactionRepositoryInterface):
        self.repo = repo

    async def execute(
        self,
        status: Optional[TransactionStatus] = None,
        user_id: Optional[UUID] = None,
        bank_account_origin_id: Optional[UUID] = None,
        bank_account_destination_id: Optional[UUID] = None,
        created_at_from: Optional[datetime] = None,
        created_at_to: Optional[datetime] = None,
    ) -> List[TransactionReadDTO]:
        query_filter = _build_transaction_query_filter(
            status=status,
            user_id=user_id,
            bank_account_origin_id=bank_account_origin_id,
            bank_account_destination_id=bank_account_destination_id,
            created_at_from=created_at_from,
            created_at_to=created_at_to,
        )
        items = await self.repo.list(query_filter=query_filter)
        return [TransactionReadDTO.model_validate(x) for x in items]


class CreateTransactionUseCase:
    def __init__(self, repo: TransactionRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: TransactionCreateCmd) -> TransactionReadDTO:
        entity_data = _cmd_to_entity_data(cmd.model_dump())
        # Si checked=True, status pasa a "checked"
        if entity_data.get("checked") is True:
            entity_data["status"] = TransactionStatus.checked
        entity = Transaction(**entity_data)
        saved = await self.repo.add(entity)
        await self.repo.commit()
        await self.repo.refresh(saved)
        return TransactionReadDTO.model_validate(saved)


class UpdateTransactionUseCase:
    def __init__(self, repo: TransactionRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: TransactionUpdateCmd) -> Optional[TransactionReadDTO]:
        entity = await self.repo.get(cmd.id)
        if not entity:
            return None

        updates = _cmd_to_entity_data(cmd.model_dump(exclude_unset=True))
        # No actualizar checked si es None (el modelo requiere bool)
        updates = {k: v for k, v in updates.items() if k != "checked" or v is not None}
        # Si checked=True, status pasa a "checked"
        if updates.get("checked") is True:
            updates["status"] = TransactionStatus.checked
        for attr, value in updates.items():
            setattr(entity, attr, value)

        await self.repo.update(entity)
        await self.repo.commit()
        await self.repo.refresh(entity)
        return TransactionReadDTO.model_validate(entity)


class DeleteTransactionUseCase:
    def __init__(self, repo: TransactionRepositoryInterface):
        self.repo = repo

    async def execute(self, transaction_id: UUID) -> None:
        await self.repo.delete(transaction_id)
        await self.repo.commit()


class ImportTransactionsUseCase:
    """Caso de uso para recibir archivo de importación. Valida formato y retorna metadata.
    Usa CreateTransactionUseCase, CreateUserUseCase y CreateBankAccountUseCase para crear entidades al importar.
    """

    def __init__(
        self,
        create_transaction_uc: "CreateTransactionUseCase",
        create_user_uc: "CreateUserUseCase",
        create_bank_account_uc: "CreateBankAccountUseCase",
    ):
        self._create_transaction = create_transaction_uc
        self._create_user = create_user_uc
        self._create_bank_account = create_bank_account_uc

    async def execute(self, body: ImportRequestCmd) -> ImportResponseDTO:
        """Procesa la importación: por cada item crea user_origin+bank_account_origin, user_destination+bank_account_destination,
        y transaction. Cada usuario se relaciona directamente con su bank_account.
        """
        from app.modules.transactions.application.schemas.bank_account_schema import BankAccountCreateCmd
        from app.modules.users.application.schemas.user_schema import UserCreateCmd

        created_users = 0
        created_bank_accounts = 0
        created_transactions = 0

        for item in body.items:
            # Emisor: user_origin + bank_account_origin (cada bank_account pertenece a su user)
            user_origin_cmd = UserCreateCmd.model_validate(item.user_origin.user)
            user_origin_dto = await self._create_user.execute(user_origin_cmd, profile_image=None)
            user_origin_id = user_origin_dto.id
            created_users += 1

            bank_origin_data = item.user_origin.bank_account.model_dump()
            bank_origin_data["user_id"] = user_origin_id
            bank_origin_cmd = BankAccountCreateCmd.model_validate(bank_origin_data)
            bank_origin_dto = await self._create_bank_account.execute(bank_origin_cmd)
            created_bank_accounts += 1

            # Receptor: user_destination + bank_account_destination
            user_dest_cmd = UserCreateCmd.model_validate(item.user_destination.user)
            user_dest_dto = await self._create_user.execute(user_dest_cmd, profile_image=None)
            user_dest_id = user_dest_dto.id
            created_users += 1

            bank_dest_data = item.user_destination.bank_account.model_dump()
            bank_dest_data["user_id"] = user_dest_id
            bank_dest_cmd = BankAccountCreateCmd.model_validate(bank_dest_data)
            bank_dest_dto = await self._create_bank_account.execute(bank_dest_cmd)
            created_bank_accounts += 1

            # Transaction: user_id = emisor, code = autogenerado
            txn_data = item.transaction.model_dump()
            txn_data["user_id"] = user_origin_id
            txn_data["bank_account_origin"] = bank_origin_dto.id
            txn_data["bank_account_destination"] = bank_dest_dto.id
            txn_data["code"] = f"TXN-{uuid4().hex[:12].upper()}"
            txn_cmd = TransactionCreateCmd.model_validate(txn_data)
            await self._create_transaction.execute(txn_cmd)
            created_transactions += 1

        return ImportResponseDTO(
            created_transactions=created_transactions,
            created_users=created_users,
            created_bank_accounts=created_bank_accounts,
        )
