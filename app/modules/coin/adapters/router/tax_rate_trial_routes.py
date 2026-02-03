# app/modules/coin/adapters/router/tax_rate_trial_routes.py
from fastapi import APIRouter, HTTPException, status
from uuid import UUID
from typing import List

from app.modules.coin.application.schemas import (
    TaxRateTrialCreateCmd,
    TaxRateTrialUpdateCmd,
    TaxRateTrialReadDTO,
)
from app.modules.coin.adapters.dependencies import (
    GetTaxRateTrialByIdUseCaseDep,
    ListTaxRateTrialsUseCaseDep,
    CreateTaxRateTrialUseCaseDep,
    UpdateTaxRateTrialUseCaseDep,
    DeleteTaxRateTrialUseCaseDep,
)

router = APIRouter(prefix="/tax-rate-trial", tags=["tax-rate-trial"])


@router.get("", response_model=List[TaxRateTrialReadDTO])
async def list_tax_rate_trials(use_case: ListTaxRateTrialsUseCaseDep):
    return await use_case.execute()


@router.get("/{tax_rate_trial_id}", response_model=TaxRateTrialReadDTO)
async def get_tax_rate_trial_by_id(tax_rate_trial_id: UUID, use_case: GetTaxRateTrialByIdUseCaseDep):
    entity = await use_case.execute(tax_rate_trial_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Tasa prueba no encontrada")
    return entity


@router.post("", response_model=TaxRateTrialReadDTO, status_code=status.HTTP_201_CREATED)
async def create_tax_rate_trial(cmd: TaxRateTrialCreateCmd, use_case: CreateTaxRateTrialUseCaseDep):
    try:
        return await use_case.execute(cmd)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("", response_model=TaxRateTrialReadDTO)
async def update_tax_rate_trial(cmd: TaxRateTrialUpdateCmd, use_case: UpdateTaxRateTrialUseCaseDep):
    entity = await use_case.execute(cmd)
    if not entity:
        raise HTTPException(status_code=404, detail="Tasa prueba no encontrada")
    return entity


@router.delete("/{tax_rate_trial_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tax_rate_trial(tax_rate_trial_id: UUID, use_case: DeleteTaxRateTrialUseCaseDep):
    await use_case.execute(tax_rate_trial_id)
