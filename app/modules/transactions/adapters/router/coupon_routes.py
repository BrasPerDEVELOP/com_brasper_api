# app/modules/transactions/adapters/router/coupon_routes.py
from uuid import UUID
from typing import List

from fastapi import APIRouter, HTTPException, status

from app.modules.transactions.application.schemas import (
    CouponCreateCmd,
    CouponUpdateCmd,
    CouponReadDTO,
)
from app.modules.transactions.adapters.dependencies import (
    GetCouponByIdUseCaseDep,
    ListCouponsUseCaseDep,
    CreateCouponUseCaseDep,
    UpdateCouponUseCaseDep,
    DeleteCouponUseCaseDep,
)

router = APIRouter(prefix="/coupons", tags=["coupons"])


@router.get("/", response_model=List[CouponReadDTO])
async def list_coupons(use_case: ListCouponsUseCaseDep):
    return await use_case.execute()


@router.get("/{coupon_id}", response_model=CouponReadDTO)
async def get_coupon_by_id(coupon_id: UUID, use_case: GetCouponByIdUseCaseDep):
    entity = await use_case.execute(coupon_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Cupón no encontrado")
    return entity


@router.post("/", response_model=CouponReadDTO, status_code=status.HTTP_201_CREATED)
async def create_coupon(cmd: CouponCreateCmd, use_case: CreateCouponUseCaseDep):
    try:
        return await use_case.execute(cmd)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/", response_model=CouponReadDTO)
async def update_coupon(cmd: CouponUpdateCmd, use_case: UpdateCouponUseCaseDep):
    entity = await use_case.execute(cmd)
    if not entity:
        raise HTTPException(status_code=404, detail="Cupón no encontrado")
    return entity


@router.delete("/{coupon_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_coupon(coupon_id: UUID, use_case: DeleteCouponUseCaseDep):
    await use_case.execute(coupon_id)
