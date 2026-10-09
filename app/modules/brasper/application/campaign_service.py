"""Versioned campaign administration over Brasper's authoritative coupon ledger."""
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select

from app.modules.transactions.domain.models import Coupon, CouponCampaignVersion
from app.modules.transactions.application.schemas.campaign_schema import CampaignDraft


class CampaignConflict(ValueError):
    pass


class CampaignService:
    def __init__(self, session):
        self.session = session

    async def _coupon(self, coupon_id, lock=False):
        stmt = select(Coupon).where(Coupon.id == coupon_id, Coupon.deleted.is_(False), Coupon.coupon_type == "CAMPAIGN")
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        coupon = (await self.session.execute(stmt)).scalar_one_or_none()
        if not coupon:
            raise KeyError("Campaña no encontrada")
        return coupon

    async def history(self, coupon_id):
        await self._coupon(coupon_id)
        rows = (await self.session.scalars(select(CouponCampaignVersion).where(
            CouponCampaignVersion.coupon_id == coupon_id).order_by(CouponCampaignVersion.version.desc()))).all()
        return [{"version": r.version, "draft": r.payload, "author": r.created_by,
                 "created_at": r.created_at.isoformat()} for r in rows]

    async def list(self):
        coupons = (await self.session.scalars(select(Coupon).where(
            Coupon.coupon_type == "CAMPAIGN", Coupon.deleted.is_(False)).order_by(Coupon.created_at.desc()))).all()
        result = []
        for coupon in coupons:
            latest = (await self.session.scalars(select(CouponCampaignVersion).where(
                CouponCampaignVersion.coupon_id == coupon.id,
                CouponCampaignVersion.version == coupon.campaign_version))).one()
            result.append({"id": str(coupon.id), "version": coupon.campaign_version,
                           "published_version": coupon.published_version, "active": coupon.is_active,
                           "used_count": coupon.used_count, "draft": latest.payload})
        return result

    async def save(self, draft: CampaignDraft, actor: str, coupon_id: UUID | None = None, expected_version: int = 0):
        if coupon_id:
            coupon = await self._coupon(coupon_id, lock=True)
            if coupon.campaign_version != expected_version:
                raise CampaignConflict("La campaña cambió; recarga antes de guardar")
            # Code is the stable coupon identifier used by advisors and existing operations.
            if draft.code != coupon.code:
                raise ValueError("El código de una campaña existente no puede cambiar")
            coupon.campaign_version += 1
        else:
            if expected_version != 0:
                raise CampaignConflict("Una campaña nueva comienza en versión cero")
            coupon = Coupon(id=uuid4(), **draft.model_dump(exclude={"campaign_rules"}),
                            campaign_rules=draft.campaign_rules.model_dump(mode="json"),
                            campaign_version=1, published_version=None, coupon_type="CAMPAIGN",
                            lifecycle_status="DRAFT", is_active=False, used_count=0, created_by=actor)
            self.session.add(coupon)
        self.session.add(CouponCampaignVersion(coupon_id=coupon.id, version=coupon.campaign_version,
                                               payload=draft.model_dump(mode="json"), created_by=actor))
        await self.session.commit()
        return {"id": str(coupon.id), "version": coupon.campaign_version}

    async def publish(self, coupon_id, version, actor):
        coupon = await self._coupon(coupon_id, lock=True)
        row = (await self.session.scalars(select(CouponCampaignVersion).where(
            CouponCampaignVersion.coupon_id == coupon_id, CouponCampaignVersion.version == version))).first()
        if not row:
            raise KeyError("Versión no encontrada")
        draft = CampaignDraft.model_validate(row.payload)
        if draft.end_date <= datetime.now(timezone.utc):
            raise ValueError("La campaña ya venció")
        if draft.max_uses < coupon.used_count:
            raise ValueError("El límite no puede ser menor que los usos ya reservados/consumidos")
        for key, value in draft.model_dump(exclude={"campaign_rules"}).items():
            setattr(coupon, key, value)
        coupon.campaign_rules = draft.campaign_rules.model_dump(mode="json")
        coupon.published_version = version
        coupon.is_active = True
        coupon.lifecycle_status = "ACTIVE"
        await self.session.commit()
        return {"ok": True, "published_version": version}

    async def disable(self, coupon_id):
        coupon = await self._coupon(coupon_id, lock=True)
        coupon.is_active = False
        await self.session.commit()
        return {"ok": True}
