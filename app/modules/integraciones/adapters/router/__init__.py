# app/modules/integraciones/adapters/router
from fastapi import APIRouter

from app.modules.integraciones.adapters.router.integration_routes import router as integration_router
from app.modules.integraciones.adapters.router.oauth_routes import router as oauth_router

router = APIRouter(prefix="/integraciones")
router.include_router(integration_router)
router.include_router(oauth_router)

__all__ = ["router"]
