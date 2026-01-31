# app/modules/transactions/adapters/router
from fastapi import APIRouter

from app.modules.transactions.adapters.router.transaction_routes import router as transaction_router
from app.modules.transactions.adapters.router.bank_routes import router as bank_router
from app.modules.transactions.adapters.router.bank_account_routes import router as bank_account_router
from app.modules.transactions.adapters.router.coupon_routes import router as coupon_router

router = APIRouter(prefix="/transactions")
router.include_router(transaction_router)
router.include_router(bank_router)
router.include_router(bank_account_router)
router.include_router(coupon_router)

__all__ = ["router"]
