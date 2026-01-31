# app/modules/coin/adapters/router/commission_routes.py
from fastapi import APIRouter, HTTPException, status
from uuid import UUID
from typing import List

from app.modules.coin.application.schemas import (
    CommissionCreateCmd,
    CommissionUpdateCmd,
    CommissionReadDTO,
)
from app.modules.coin.adapters.dependencies import (
    GetCommissionByIdUseCaseDep,
    ListCommissionsUseCaseDep,
    CreateCommissionUseCaseDep,
    UpdateCommissionUseCaseDep,
    DeleteCommissionUseCaseDep,
)

router = APIRouter(prefix="/commission", tags=["commission"])


@router.get("", response_model=List[CommissionReadDTO])
async def list_commissions(use_case: ListCommissionsUseCaseDep):
    return await use_case.execute()


@router.get("/{commission_id}", response_model=CommissionReadDTO)
async def get_commission_by_id(commission_id: UUID, use_case: GetCommissionByIdUseCaseDep):
    entity = await use_case.execute(commission_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Comisión no encontrada")
    return entity


@router.post("", response_model=CommissionReadDTO, status_code=status.HTTP_201_CREATED)
async def create_commission(cmd: CommissionCreateCmd, use_case: CreateCommissionUseCaseDep):
    try:
        return await use_case.execute(cmd)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("", response_model=CommissionReadDTO)
async def update_commission(cmd: CommissionUpdateCmd, use_case: UpdateCommissionUseCaseDep):
    entity = await use_case.execute(cmd)
    if not entity:
        raise HTTPException(status_code=404, detail="Comisión no encontrada")
    return entity


@router.delete("/{commission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_commission(commission_id: UUID, use_case: DeleteCommissionUseCaseDep):
    await use_case.execute(commission_id)
