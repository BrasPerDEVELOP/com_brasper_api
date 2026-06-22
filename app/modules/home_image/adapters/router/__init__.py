# app/modules/home_image/adapters/router
from fastapi import APIRouter

from app.modules.home_image.adapters.router.home_banner_routes import router as home_banner_routes
from app.modules.home_image.adapters.router.home_popup_routes import router as home_popup_routes

router = APIRouter(prefix="/home-banner")
router.include_router(home_banner_routes)
router.include_router(home_popup_routes)

__all__ = ["router"]
