# app/modules/coin/domain/enums.py
"""Enums para el módulo de monedas."""
import enum
from typing import Dict, Any

from sqlalchemy import Enum as SaEnum


class Currency(str, enum.Enum):
    """Código ISO de moneda con nombre y símbolo."""
    pen = "PEN"  # Sol Peruano
    brl = "BRL"  # Real Brasileño
    usd = "USD"  # Dólar

    @property
    def display_name(self) -> str:
        return currency_display[self.value]["name"]

    @property
    def symbol(self) -> str:
        return currency_display[self.value]["symbol"]

    def to_dto(self) -> Dict[str, Any]:
        return {
            "code": self.value,
            "name": self.display_name,
            "symbol": self.symbol,
        }


currency_display: Dict[str, Dict[str, str]] = {
    "PEN": {"name": "Sol Peruano", "symbol": "S/."},
    "BRL": {"name": "Real Brasileño", "symbol": "R$"},
    "USD": {"name": "Dólar", "symbol": "$"},
}

# Tipo ENUM de PostgreSQL en esquema coin (creado por migraciones).
CurrencyEnumType = SaEnum(Currency, name="currency", schema="coin", create_type=False)
