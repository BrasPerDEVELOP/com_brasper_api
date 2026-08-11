# app/modules/transactions/adapters/router
from fastapi import APIRouter

from app.modules.transactions.adapters.router.transaction_routes import router as transaction_router
from app.modules.transactions.adapters.router.bank_routes import router as bank_router
from app.modules.transactions.adapters.router.bank_account_routes import router as bank_account_router
from app.modules.transactions.adapters.router.coupon_routes import router as coupon_router
from app.modules.transactions.adapters.router.tag_routes import router as tag_router

router = APIRouter()
# Los catálogos estáticos deben registrarse antes de /{transaction_id}; de lo
# contrario una URL canónica como /transactions/banks se interpreta como UUID.
router.include_router(bank_router, prefix="/transactions")
router.include_router(bank_account_router, prefix="/transactions")
router.include_router(coupon_router, prefix="/transactions")
router.include_router(tag_router, prefix="/transactions")
router.include_router(transaction_router, prefix="/transactions")

__all__ = ["router"]
