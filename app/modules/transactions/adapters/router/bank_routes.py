# app/modules/transactions/adapters/router/bank_routes.py
from uuid import UUID
from typing import List

from fastapi import APIRouter, HTTPException, status

from app.modules.transactions.application.schemas import (
    BankCreateCmd,
    BankUpdateCmd,
    BankReadDTO,
    BanksByCountryCurrencyDTO,
)
from app.modules.transactions.adapters.dependencies import (
    GetBankByIdUseCaseDep,
    ListBanksUseCaseDep,
    ListBanksByCountryCurrencyUseCaseDep,
    CreateBankUseCaseDep,
    UpdateBankUseCaseDep,
    DeleteBankUseCaseDep,
)

router = APIRouter(prefix="/banks", tags=["banks"])


@router.get("/", response_model=List[BankReadDTO])
async def list_banks(use_case: ListBanksUseCaseDep):
    return await use_case.execute()


@router.get("/by-country-currency", response_model=BanksByCountryCurrencyDTO)
async def list_banks_by_country_currency(use_case: ListBanksByCountryCurrencyUseCaseDep):
    """Devuelve bancos agrupados por país (PE, BR) y moneda (PEN, USD, BRL)."""
    return await use_case.execute()


@router.get("/{bank_id}", response_model=BankReadDTO)
async def get_bank_by_id(bank_id: UUID, use_case: GetBankByIdUseCaseDep):
    entity = await use_case.execute(bank_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Banco no encontrado")
    return entity


@router.post("/", response_model=BankReadDTO, status_code=status.HTTP_201_CREATED)
async def create_bank(cmd: BankCreateCmd, use_case: CreateBankUseCaseDep):
    try:
        return await use_case.execute(cmd)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/", response_model=BankReadDTO)
async def update_bank(cmd: BankUpdateCmd, use_case: UpdateBankUseCaseDep):
    entity = await use_case.execute(cmd)
    if not entity:
        raise HTTPException(status_code=404, detail="Banco no encontrado")
    return entity


@router.delete("/{bank_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bank(bank_id: UUID, use_case: DeleteBankUseCaseDep):
    await use_case.execute(bank_id)
