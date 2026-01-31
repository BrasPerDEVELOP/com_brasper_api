# app/modules/coin/application/schemas/coin_schema.py
from typing import Optional

from pydantic import BaseModel


class CurrencyReadDTO(BaseModel):
    """Moneda para lectura (desde enum)."""
    code: str
    name: str
    symbol: Optional[str] = None
