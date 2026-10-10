"""Casos de uso CRUD para Coupon."""
from datetime import datetime, timezone
from uuid import UUID
from typing import List, Optional
from app.modules.transactions.application.campaign_policy import validate_campaign_dates

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

    async def execute(self, automatic_only: bool = False) -> List[CouponReadDTO]:
        from app.shared.query_filter import QueryFilter, FilterSchema, OperatorEnum

        query_filter = None
        if automatic_only:
            now = datetime.now(timezone.utc)
            query_filter = QueryFilter(
                filters=[
                    FilterSchema(field="is_active", value=True, operator=OperatorEnum.EQ),
                ]
            )
            # Filtro adicional: vigencia (start_date <= now, end_date >= now o null)
            # Se aplica en el repo o aquí; el repo base usa QueryFilter.
            # Para fechas complejas, usamos un método custom en el repo.
            items = await self.repo.list(query_filter=query_filter)
            # Filtrar por vigencia en memoria (start_date/end_date)
            result = []
            for x in items:
                if getattr(x, "campaign_rules", None) or x.per_user_limit:
                    continue  # Personalized campaigns require identity/amount eligibility.
                if x.start_date and x.start_date > now:
                    continue
                if x.end_date and x.end_date < now:
                    continue
                if x.lifecycle_status != "ACTIVE" or x.used_count >= x.max_uses:
                    continue
                result.append(CouponReadDTO.model_validate(x))
            return result
        items = await self.repo.list()
        return [CouponReadDTO.model_validate(x) for x in items]


class CreateCouponUseCase:
    def __init__(self, repo: CouponRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: CouponCreateCmd) -> CouponReadDTO:
        if cmd.campaign_rules or cmd.coupon_type == "CAMPAIGN":
            # Las campañas viven solo en com_brasper_ia; la API no crea cupones de campaña.
            raise ValueError("Las campañas se gestionan en la plataforma IA; no se crean como cupones")
        entity = Coupon(
            code=cmd.code,
            discount_percentage=cmd.discount_percentage,
            max_uses=cmd.max_uses,
            origin_currency=cmd.origin_currency,
            destination_currency=cmd.destination_currency,
            start_date=cmd.start_date,
            end_date=cmd.end_date,
            is_active=cmd.is_active,
            coupon_type=cmd.coupon_type,
            lifecycle_status=cmd.lifecycle_status,
            per_user_limit=cmd.per_user_limit,
            exchange_rate_scopes=cmd.exchange_rate_scopes,
            campaign_rules=cmd.campaign_rules.model_dump(mode="json") if cmd.campaign_rules else None,
            campaign_version=1,
        )
        saved = await self.repo.add(entity)
        await self.repo.commit()
        await self.repo.refresh(saved)
        return CouponReadDTO.model_validate(saved)


class UpdateCouponUseCase:
    def __init__(self, repo: CouponRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: CouponUpdateCmd) -> Optional[CouponReadDTO]:
        entity = await self.repo.get_for_update(cmd.id)
        if not entity:
            return None
        version = getattr(entity, "campaign_version", 1)
        if entity.coupon_type == "CAMPAIGN" or cmd.campaign_rules:
            raise ValueError("Las campañas se gestionan en la plataforma IA; esta promoción no se modifica como cupón")
        if (getattr(entity, "campaign_rules", None) or cmd.campaign_rules) and cmd.expected_version != version:
            raise ValueError("La campaña cambió; recarga antes de guardar")
        if cmd.expected_version is not None and cmd.expected_version != version:
            raise ValueError("La campaña cambió; recarga antes de guardar")
        if cmd.campaign_rules:
            entity.campaign_rules = cmd.campaign_rules.model_dump(mode="json")
        if cmd.code is not None:
            entity.code = cmd.code
        if cmd.discount_percentage is not None:
            entity.discount_percentage = cmd.discount_percentage
        if cmd.max_uses is not None:
            # C1: same rule as campaign publication; the quota cannot drop below
            # usages already reserved (pending) or consumed (completed).
            if cmd.max_uses < (entity.used_count or 0):
                raise ValueError("El límite no puede ser menor que los usos ya reservados/consumidos")
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
        if cmd.lifecycle_status is not None:
            entity.lifecycle_status = cmd.lifecycle_status
        if cmd.per_user_limit is not None:
            entity.per_user_limit = cmd.per_user_limit
        if cmd.exchange_rate_scopes is not None:
            entity.exchange_rate_scopes = cmd.exchange_rate_scopes
        if getattr(entity, "campaign_rules", None):
            validate_campaign_dates(entity.start_date, entity.end_date)
        entity.campaign_version = version + 1
        await self.repo.update(entity)
        await self.repo.commit()
        await self.repo.refresh(entity)
        return CouponReadDTO.model_validate(entity)


class DeleteCouponUseCase:
    def __init__(self, repo: CouponRepositoryInterface):
        self.repo = repo

    async def execute(self, coupon_id: UUID) -> None:
        entity = await self.repo.get_for_update(coupon_id)
        if entity is not None and entity.coupon_type == "CAMPAIGN":
            # C1: campaign rows (migración 083) keep their history; never deleted from coupons.
            raise ValueError("Las campañas no se eliminan desde cupones; su historial se conserva")
        await self.repo.delete(coupon_id)
        await self.repo.commit()
