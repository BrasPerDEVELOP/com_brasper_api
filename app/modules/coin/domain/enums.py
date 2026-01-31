# app/modules/coin/domain/enums.py
"""Enums para el módulo de monedas."""
import enum
from typing import Dict, Any


class Currency(str, enum.Enum):
    """Código ISO de moneda con nombre y símbolo."""
    pen = "pen"  # Sol Peruano
    brl = "brl"  # Real Brasileño
    usd = "usd"  # Dólar

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
    "pen": {"name": "Sol Peruano", "symbol": "S/."},
    "brl": {"name": "Real Brasileño", "symbol": "R$"},
    "usd": {"name": "Dólar", "symbol": "$"},
}
