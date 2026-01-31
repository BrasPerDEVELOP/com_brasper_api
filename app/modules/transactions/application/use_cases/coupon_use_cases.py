"""Casos de uso CRUD para Coupon."""
from uuid import UUID
from typing import List, Optional

from app.modules.transactions.domain.models import Coupon
from app.modules.transactions.interfaces.coupon_repository import CouponRepositoryInterface
from app.modules.transactions.application.schemas.coupon_schema import (
    CouponCreateCmd,
    CouponUpdateCmd,
    CouponReadDTO,
)


class GetCouponByIdUseCase:
    def __init__(self, repo: CouponRepositoryInterface):
        self.repo = repo

    async def execute(self, coupon_id: UUID) -> Optional[CouponReadDTO]:
        entity = await self.repo.get(coupon_id)
        if not entity:
            return None
        return CouponReadDTO.model_validate(entity)


class ListCouponsUseCase:
    def __init__(self, repo: CouponRepositoryInterface):
        self.repo = repo

    async def execute(self) -> List[CouponReadDTO]:
        items = await self.repo.list()
        return [CouponReadDTO.model_validate(x) for x in items]


class CreateCouponUseCase:
    def __init__(self, repo: CouponRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: CouponCreateCmd) -> CouponReadDTO:
        entity = Coupon(
            code=cmd.code,
            discount_percentage=cmd.discount_percentage,
            max_uses=cmd.max_uses,
            origin_currency=cmd.origin_currency,
            destination_currency=cmd.destination_currency,
            start_date=cmd.start_date,
            end_date=cmd.end_date,
            is_active=cmd.is_active,
        )
        saved = await self.repo.add(entity)
        await self.repo.commit()
        await self.repo.refresh(saved)
        return CouponReadDTO.model_validate(saved)


class UpdateCouponUseCase:
    def __init__(self, repo: CouponRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: CouponUpdateCmd) -> Optional[CouponReadDTO]:
        entity = await self.repo.get(cmd.id)
        if not entity:
            return None
        if cmd.code is not None:
            entity.code = cmd.code
        if cmd.discount_percentage is not None:
            entity.discount_percentage = cmd.discount_percentage
        if cmd.max_uses is not None:
            entity.max_uses = cmd.max_uses
        if cmd.origin_currency is not None:
            entity.origin_currency = cmd.origin_currency
        if cmd.destination_currency is not None:
            entity.destination_currency = cmd.destination_currency
        if cmd.start_date is not None:
            entity.start_date = cmd.start_date
        if cmd.end_date is not None:
            entity.end_date = cmd.end_date
        if cmd.is_active is not None:
            entity.is_active = cmd.is_active
        await self.repo.update(entity)
        await self.repo.commit()
        await self.repo.refresh(entity)
        return CouponReadDTO.model_validate(entity)


class DeleteCouponUseCase:
    def __init__(self, repo: CouponRepositoryInterface):
        self.repo = repo

    async def execute(self, coupon_id: UUID) -> None:
        await self.repo.delete(coupon_id)
        await self.repo.commit()
