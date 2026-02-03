# app/modules/coin/adapters/router
from fastapi import APIRouter

from app.modules.coin.adapters.router.currencies_routes import router as currencies_router
from app.modules.coin.adapters.router.tax_rate_routes import router as tax_rate_router
from app.modules.coin.adapters.router.tax_rate_trial_routes import router as tax_rate_trial_router
from app.modules.coin.adapters.router.commission_routes import router as commission_router

router = APIRouter(prefix="/coin")
router.include_router(currencies_router)
router.include_router(tax_rate_router)
router.include_router(tax_rate_trial_router)
router.include_router(commission_router)

__all__ = ["router"]
