# app/modules/coin/adapters/router/tax_rate_routes.py
from fastapi import APIRouter, HTTPException, status
from uuid import UUID
from typing import List

from app.modules.coin.application.schemas import (
    TaxRateCreateCmd,
    TaxRateUpdateCmd,
    TaxRateReadDTO,
)
from app.modules.coin.adapters.dependencies import (
    GetTaxRateByIdUseCaseDep,
    ListTaxRatesUseCaseDep,
    CreateTaxRateUseCaseDep,
    UpdateTaxRateUseCaseDep,
    DeleteTaxRateUseCaseDep,
)

router = APIRouter(prefix="/tax-rate", tags=["tax-rate"])


@router.get("", response_model=List[TaxRateReadDTO])
async def list_tax_rates(use_case: ListTaxRatesUseCaseDep):
    return await use_case.execute()


@router.get("/{tax_rate_id}", response_model=TaxRateReadDTO)
async def get_tax_rate_by_id(tax_rate_id: UUID, use_case: GetTaxRateByIdUseCaseDep):
    entity = await use_case.execute(tax_rate_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Tasa no encontrada")
    return entity


@router.post("", response_model=TaxRateReadDTO, status_code=status.HTTP_201_CREATED)
async def create_tax_rate(cmd: TaxRateCreateCmd, use_case: CreateTaxRateUseCaseDep):
    try:
        return await use_case.execute(cmd)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("", response_model=TaxRateReadDTO)
async def update_tax_rate(cmd: TaxRateUpdateCmd, use_case: UpdateTaxRateUseCaseDep):
    entity = await use_case.execute(cmd)
    if not entity:
        raise HTTPException(status_code=404, detail="Tasa no encontrada")
    return entity


@router.delete("/{tax_rate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tax_rate(tax_rate_id: UUID, use_case: DeleteTaxRateUseCaseDep):
    await use_case.execute(tax_rate_id)
