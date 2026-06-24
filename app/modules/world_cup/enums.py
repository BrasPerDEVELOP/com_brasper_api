from __future__ import annotations

from enum import Enum
from typing import Iterable

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

    @classmethod
    def normalize_many(
        cls,
        scopes: Iterable[str | "ExchangeRateScope"] | None,
        *,
        fallback: "ExchangeRateScope" | None = None,
    ) -> list["ExchangeRateScope"]:
        parsed: list[ExchangeRateScope] = []
        for item in scopes or []:
            try:
                scope = item if isinstance(item, cls) else cls(str(item))
            except ValueError:
                continue
            if scope not in parsed:
                parsed.append(scope)
        if cls.all in parsed:
            return [cls.all]
        if parsed:
            return parsed
        return [fallback or cls.pen_brl]

    @classmethod
    def matches_pair(
        cls,
        scopes: Iterable[str | "ExchangeRateScope"] | None,
        origin: str | Currency,
        destination: str | Currency,
    ) -> bool:
        normalized = cls.normalize_many(scopes)
        if cls.all in normalized:
            return True
        origin_value = origin.value if isinstance(origin, Currency) else origin
        destination_value = destination.value if isinstance(destination, Currency) else destination
        return f"{origin_value}_{destination_value}" in {scope.value for scope in normalized}
