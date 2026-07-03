# app/modules/metrics/adapters/router
from fastapi import APIRouter

from app.modules.metrics.adapters.router.metrics_routes import router as weekly_router

router = APIRouter(prefix="/metrics")
router.include_router(weekly_router)

__all__ = ["router"]
