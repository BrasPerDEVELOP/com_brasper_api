# app/modules/transactions/adapters/router/coupon_routes.py
from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

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

from app.core.routing import LegacyAliasRouter
from app.modules.auth.infrastructure.dependencies import require_permission

router = LegacyAliasRouter(prefix="/coupons", tags=["coupons"])


@router.get("", response_model=List[CouponReadDTO])
async def list_coupons(
    use_case: ListCouponsUseCaseDep,
    _permissions=Depends(require_permission("coupons.view")),
):
    return await use_case.execute()


@router.get("/automatic", response_model=List[CouponReadDTO])
async def list_automatic_coupons(use_case: ListCouponsUseCaseDep):
    """Lista cupones activos y vigentes (para aplicación automática)."""
    return await use_case.execute(automatic_only=True)


@router.get("/{coupon_id}", response_model=CouponReadDTO)
async def get_coupon_by_id(
    coupon_id: UUID,
    use_case: GetCouponByIdUseCaseDep,
    _permissions=Depends(require_permission("coupons.view")),
):
    entity = await use_case.execute(coupon_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Cupón no encontrado")
    return entity


from app.modules.audit.infrastructure.stage_mutation_audit import stage_mutation_audit


@router.post("", response_model=CouponReadDTO, status_code=status.HTTP_201_CREATED)
async def create_coupon(
    cmd: CouponCreateCmd,
    use_case: CreateCouponUseCaseDep,
    _permissions=Depends(require_permission("coupons.create")),
    audit_event=Depends(stage_mutation_audit("coupons.create", "coupon")),
):
    try:
        created = await use_case.execute(cmd)
        if audit_event and created:
            audit_event.entity_id = str(created.id)
            audit_event.new_values = cmd.model_dump(mode="json")
        return created
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("", response_model=CouponReadDTO)
async def update_coupon(
    cmd: CouponUpdateCmd,
    use_case: UpdateCouponUseCaseDep,
    get_use_case: GetCouponByIdUseCaseDep,
    _permissions=Depends(require_permission("coupons.update")),
    audit_event=Depends(stage_mutation_audit("coupons.update", "coupon")),
):
    previous = await get_use_case.execute(cmd.id)
    if audit_event and previous:
        audit_event.old_values = previous.model_dump(mode="json")
    entity = await use_case.execute(cmd)
    if audit_event and entity:
        audit_event.entity_id = str(entity.id)
        audit_event.new_values = cmd.model_dump(mode="json")
    if not entity:
        raise HTTPException(status_code=404, detail="Cupón no encontrado")
    return entity


@router.delete("/{coupon_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_coupon(
    coupon_id: UUID,
    use_case: DeleteCouponUseCaseDep,
    get_use_case: GetCouponByIdUseCaseDep,
    _permissions=Depends(require_permission("coupons.delete")),
    audit_event=Depends(stage_mutation_audit("coupons.delete", "coupon")),
):
    previous = await get_use_case.execute(coupon_id)
    if audit_event:
        audit_event.entity_id = str(coupon_id)
        audit_event.old_values = previous.model_dump(mode="json") if previous else None
    await use_case.execute(coupon_id)
