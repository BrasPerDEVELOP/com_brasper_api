from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.modules.coin.domain.models import Commission, TaxRate
from app.modules.home_image.domain.models import HomeBanner

router = APIRouter(tags=["home-bootstrap"])


@router.get("/home-bootstrap")
async def home_bootstrap(db: AsyncSession = Depends(get_db)):
    banner = (await db.execute(select(HomeBanner).where(HomeBanner.deleted.is_(False), HomeBanner.enable.is_(True)).order_by(HomeBanner.updated_at.desc()))).scalars().first()
    rates = (await db.execute(select(TaxRate).where(TaxRate.deleted.is_(False), TaxRate.enable.is_(True)))).scalars().all()
    commissions = (await db.execute(select(Commission).where(Commission.deleted.is_(False), Commission.enable.is_(True)))).scalars().all()
    def row(item, fields):
        return {"id": str(item.id), **{field: getattr(item, field) for field in fields}}
    return {
        "banner": row(banner, ["banner_es", "banner_pr", "banner_en", "enable", "content", "indicators", "appearance", "show_image", "show_indicators", "updated_at"]) if banner else None,
        "rates": [row(item, ["tax", "coin_a", "coin_b"]) for item in rates],
        "commissions": [row(item, ["percentage", "reverse", "min_amount", "max_amount", "coin_a", "coin_b"]) for item in commissions],
    }
