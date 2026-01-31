# app/modules/coin/adapters/router/currencies_routes.py
from fastapi import APIRouter
from typing import List

from app.modules.coin.application.schemas import CurrencyReadDTO
from app.modules.coin.domain.enums import Currency

router = APIRouter(tags=["currencies"])


@router.get("/currencies", response_model=List[CurrencyReadDTO])
async def list_currencies() -> List[CurrencyReadDTO]:
    """Lista las monedas disponibles (enum)."""
    return [CurrencyReadDTO(**c.to_dto()) for c in Currency]
