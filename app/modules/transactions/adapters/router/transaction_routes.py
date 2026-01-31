# app/modules/transactions/adapters/router/transaction_routes.py
from fastapi import APIRouter, HTTPException, status
from uuid import UUID
from typing import List

from app.modules.transactions.application.schemas import (
    TransactionCreateCmd,
    TransactionUpdateCmd,
    TransactionReadDTO,
)
from app.modules.transactions.adapters.dependencies import (
    GetTransactionByIdUseCaseDep,
    ListTransactionsUseCaseDep,
    CreateTransactionUseCaseDep,
    UpdateTransactionUseCaseDep,
    DeleteTransactionUseCaseDep,
)

router = APIRouter(tags=["transactions"])


@router.get("/", response_model=List[TransactionReadDTO])
async def list_transactions(use_case: ListTransactionsUseCaseDep):
    return await use_case.execute()


@router.get("/{transaction_id}", response_model=TransactionReadDTO)
async def get_transaction_by_id(transaction_id: UUID, use_case: GetTransactionByIdUseCaseDep):
    entity = await use_case.execute(transaction_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Transacción no encontrada")
    return entity


@router.post("/", response_model=TransactionReadDTO, status_code=status.HTTP_201_CREATED)
async def create_transaction(cmd: TransactionCreateCmd, use_case: CreateTransactionUseCaseDep):
    try:
        return await use_case.execute(cmd)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/", response_model=TransactionReadDTO)
async def update_transaction(cmd: TransactionUpdateCmd, use_case: UpdateTransactionUseCaseDep):
    entity = await use_case.execute(cmd)
    if not entity:
        raise HTTPException(status_code=404, detail="Transacción no encontrada")
    return entity


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(transaction_id: UUID, use_case: DeleteTransactionUseCaseDep):
    await use_case.execute(transaction_id)
