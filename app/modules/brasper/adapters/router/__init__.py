from fastapi import APIRouter

from app.modules.brasper.adapters.router.contact_form_routes import router as contact_form_routes
from app.modules.brasper.adapters.router.ai_routes import router as ai_routes

router = APIRouter(prefix="/brasper")
router.include_router(contact_form_routes)
router.include_router(ai_routes)

__all__ = ["router"]
