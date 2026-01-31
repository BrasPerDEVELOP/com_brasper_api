# app/modules/transactions/application/use_cases/transaction_use_cases.py
"""Casos de uso CRUD para Transaction."""
from uuid import UUID
from typing import List, Optional

from app.modules.transactions.domain.models import Transaction
from app.modules.transactions.interfaces.transaction_repository import TransactionRepositoryInterface
from app.modules.transactions.application.schemas.transaction_schema import (
    TransactionCreateCmd,
    TransactionUpdateCmd,
    TransactionReadDTO,
)


class GetTransactionByIdUseCase:
    def __init__(self, repo: TransactionRepositoryInterface):
        self.repo = repo

    async def execute(self, transaction_id: UUID) -> Optional[TransactionReadDTO]:
        entity = await self.repo.get(transaction_id)
        if not entity:
            return None
        return TransactionReadDTO.model_validate(entity)


class ListTransactionsUseCase:
    def __init__(self, repo: TransactionRepositoryInterface):
        self.repo = repo

    async def execute(self) -> List[TransactionReadDTO]:
        items = await self.repo.list()
        return [TransactionReadDTO.model_validate(x) for x in items]


class CreateTransactionUseCase:
    def __init__(self, repo: TransactionRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: TransactionCreateCmd) -> TransactionReadDTO:
        entity = Transaction(
            bank_account_id=cmd.bank_account_id,
            user_id=cmd.user_id,
            tax_rate_id=cmd.tax_rate_id,
            commission_id=cmd.commission_id,
            status=cmd.status,
            origin_amount=cmd.origin_amount,
            destination_amount=cmd.destination_amount,
            code=cmd.code,
            send_date=cmd.send_date,
            payment_date=cmd.payment_date,
            send_voucher=cmd.send_voucher,
            payment_voucher=cmd.payment_voucher,
        )
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
        if cmd.bank_account_id is not None:
            entity.bank_account_id = cmd.bank_account_id
        if cmd.user_id is not None:
            entity.user_id = cmd.user_id
        if cmd.tax_rate_id is not None:
            entity.tax_rate_id = cmd.tax_rate_id
        if cmd.commission_id is not None:
            entity.commission_id = cmd.commission_id
        if cmd.status is not None:
            entity.status = cmd.status
        if cmd.origin_amount is not None:
            entity.origin_amount = cmd.origin_amount
        if cmd.destination_amount is not None:
            entity.destination_amount = cmd.destination_amount
        if cmd.code is not None:
            entity.code = cmd.code
        if cmd.send_date is not None:
            entity.send_date = cmd.send_date
        if cmd.payment_date is not None:
            entity.payment_date = cmd.payment_date
        if cmd.send_voucher is not None:
            entity.send_voucher = cmd.send_voucher
        if cmd.payment_voucher is not None:
            entity.payment_voucher = cmd.payment_voucher
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
