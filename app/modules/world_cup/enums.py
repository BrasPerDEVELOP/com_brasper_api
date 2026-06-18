from enum import Enum

from app.modules.coin.domain.enums import Currency


class ExchangeRateScope(str, Enum):
    brl_pen = "BRL_PEN"
    pen_brl = "PEN_BRL"
    usd_brl = "USD_BRL"
    brl_usd = "BRL_USD"
    all = "ALL"

    @property
    def currencies(self) -> tuple[Currency | None, Currency | None]:
        if self is ExchangeRateScope.all:
            return None, None
        origin, destination = self.value.split("_")
        return Currency(origin), Currency(destination)

    @classmethod
    def from_currencies(cls, origin: str | Currency | None, destination: str | Currency | None) -> "ExchangeRateScope":
        origin_value = origin.value if isinstance(origin, Currency) else origin
        destination_value = destination.value if isinstance(destination, Currency) else destination
        if (origin_value, destination_value) in {(None, None), ("ALL", "ALL")}:
            return cls.all
        return cls(f"{origin_value}_{destination_value}")
