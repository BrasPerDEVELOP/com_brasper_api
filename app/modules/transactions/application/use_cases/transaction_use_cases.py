# app/modules/transactions/application/use_cases/transaction_use_cases.py
"""Casos de uso CRUD para Transaction."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy.orm import selectinload

if TYPE_CHECKING:
    from app.modules.users.application.use_cases import CreateUserUseCase
    from app.modules.transactions.application.use_cases.bank_account_use_cases import CreateBankAccountUseCase

from app.shared.query_filter import FilterSchema, OperatorEnum, QueryFilter
from app.modules.coin.interfaces.tax_rate_repository import TaxRateRepositoryInterface
from app.modules.transactions.domain.models import Transaction
from app.modules.transactions.domain.enums import TransactionStatus
from app.modules.transactions.interfaces.transaction_repository import (
    TransactionRepositoryInterface,
)
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


def _non_empty_str(value: Optional[str]) -> bool:
    return value is not None and str(value).strip() != ""


def _is_transaction_pipeline_complete(entity: Transaction) -> bool:
    """True si checklist y datos operativos (montos, send_date, vouchers) están completos.
    `payment_date` no se exige aquí: se asigna en servidor al pasar a completed."""
    return (
        entity.checked is True
        and entity.commission_result is not None
        and entity.total_to_send is not None
        and entity.send_date is not None
        and _non_empty_str(entity.send_voucher)
        and _non_empty_str(entity.payment_voucher)
    )


def sync_transaction_status_from_checklist(entity: Transaction) -> None:
    """Asigna status según checklist y completitud; no modifica transacciones fallidas.
    Al pasar a `completed` por primera vez, fija `payment_date` a ahora (UTC)."""
    previous_status = entity.status
    if entity.status == TransactionStatus.failed:
        return
    if not entity.checked:
        entity.status = TransactionStatus.verification
        return
    if _is_transaction_pipeline_complete(entity):
        if previous_status != TransactionStatus.completed:
            entity.payment_date = datetime.now(timezone.utc)
        entity.status = TransactionStatus.completed
    else:
        entity.status = TransactionStatus.verified


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


_TXN_LOAD_USER = (selectinload(Transaction.user),)


class GetTransactionByIdUseCase:
    def __init__(self, repo: TransactionRepositoryInterface):
        self.repo = repo

    async def execute(self, transaction_id: UUID) -> Optional[TransactionReadDTO]:
        entity = await self.repo.get(transaction_id, eager_options=_TXN_LOAD_USER)
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
        items = await self.repo.list(query_filter=query_filter, eager_options=_TXN_LOAD_USER)
        return [TransactionReadDTO.model_validate(x) for x in items]


class CreateTransactionUseCase:
    def __init__(
        self,
        repo: TransactionRepositoryInterface,
        tax_rate_repo: TaxRateRepositoryInterface,
    ):
        self.repo = repo
        self._tax_rate_repo = tax_rate_repo

    async def execute(self, cmd: TransactionCreateCmd) -> TransactionReadDTO:
        entity_data = _cmd_to_entity_data(cmd.model_dump())
        tax_rate = await self._tax_rate_repo.get(cmd.tax_rate_id)
        if not tax_rate:
            raise ValueError(f"No existe tax_rate con id {cmd.tax_rate_id}")
        entity_data["code"] = await self.repo.next_sequential_transaction_code(
            tax_rate.coin_a.value,
            tax_rate.coin_b.value,
        )
        # Alta: sin checklist; estado en verificación (el cliente no puede activar el check al crear)
        entity_data["checked"] = False
        entity_data["status"] = TransactionStatus.verification
        # Fecha/hora de creación de la operación (envío); no se toma del cliente
        entity_data["send_date"] = datetime.now(timezone.utc)
        entity = Transaction(**entity_data)
        sync_transaction_status_from_checklist(entity)
        saved = await self.repo.add(entity)
        await self.repo.commit()
        await self.repo.refresh(saved, load_noload_relations=["user"])
        return TransactionReadDTO.model_validate(saved)


class UpdateTransactionUseCase:
    def __init__(self, repo: TransactionRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: TransactionUpdateCmd) -> Optional[TransactionReadDTO]:
        entity = await self.repo.get(cmd.id, eager_options=_TXN_LOAD_USER)
        if not entity:
            return None

        updates = _cmd_to_entity_data(cmd.model_dump(exclude_unset=True))
        remove_send_voucher = updates.pop("remove_send_voucher", False)
        remove_payment_voucher = updates.pop("remove_payment_voucher", False)
        # No actualizar checked si es None (el modelo requiere bool)
        updates = {k: v for k, v in updates.items() if k != "checked" or v is not None}

        if remove_send_voucher:
            updates["send_voucher"] = None
        if remove_payment_voucher:
            updates["payment_voucher"] = None

        for attr, value in updates.items():
            setattr(entity, attr, value)

        sync_transaction_status_from_checklist(entity)

        await self.repo.update(entity)
        await self.repo.commit()
        await self.repo.refresh(entity, load_noload_relations=["user"])
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
        transaction_repo: TransactionRepositoryInterface,
        tax_rate_repo: TaxRateRepositoryInterface,
    ):
        self._create_transaction = create_transaction_uc
        self._create_user = create_user_uc
        self._create_bank_account = create_bank_account_uc
        self._transaction_repo = transaction_repo
        self._tax_rate_repo = tax_rate_repo

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

            # Transaction: user_id = emisor, code = secuencial PxB-0000000001 (según tasa/moneda)
            tax_rate = await self._tax_rate_repo.get(item.transaction.tax_rate_id)
            if not tax_rate:
                raise ValueError(
                    f"No existe tax_rate con id {item.transaction.tax_rate_id}"
                )
            code = await self._transaction_repo.next_sequential_transaction_code(
                tax_rate.coin_a.value,
                tax_rate.coin_b.value,
            )
            txn_data = item.transaction.model_dump()
            txn_data["user_id"] = user_origin_id
            txn_data["bank_account_origin"] = bank_origin_dto.id
            txn_data["bank_account_destination"] = bank_dest_dto.id
            txn_data["code"] = code
            txn_cmd = TransactionCreateCmd.model_validate(txn_data)
            await self._create_transaction.execute(txn_cmd)
            created_transactions += 1

        return ImportResponseDTO(
            created_transactions=created_transactions,
            created_users=created_users,
            created_bank_accounts=created_bank_accounts,
        )
