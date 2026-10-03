# app/modules/finance/interfaces/repository.py
"""Puertos de persistencia del módulo finance."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional
from uuid import UUID

from app.modules.coin.domain.enums import Currency
from app.modules.finance.domain.models import Expense, ExpenseCategory, FxMonthRate


class FinanceRepositoryInterface(ABC):
    @abstractmethod
    async def list_fx_rates(self, year: int) -> list[FxMonthRate]: ...

    @abstractmethod
    async def fx_rates_map(self, years: list[int]) -> dict[tuple[int, int, str], float]:
        """``{(año, mes, 'BRL'): tasa}`` para los años pedidos."""
        ...

    @abstractmethod
    async def upsert_fx_rate(
        self, *, year: int, month: int, currency: Currency, rate_to_pen: float
    ) -> FxMonthRate: ...

    @abstractmethod
    async def list_categories(self) -> list[ExpenseCategory]: ...

    @abstractmethod
    async def get_category(self, category_id: UUID) -> Optional[ExpenseCategory]: ...

    @abstractmethod
    async def list_expenses(
        self, *, date_from: date, date_to: date, category_id: Optional[UUID] = None
    ) -> list[Expense]: ...

    @abstractmethod
    async def get_expense(self, expense_id: UUID) -> Optional[Expense]: ...

    @abstractmethod
    async def add_expense(self, entity: Expense) -> Expense: ...

    @abstractmethod
    async def monthly_expenses(self, year: int) -> dict[int, float]:
        """``{mes: total_pen}`` del año (solo meses con gasto)."""
        ...

    @abstractmethod
    async def expenses_by_category(self, year: int, month: int) -> list[tuple[str, float]]:
        """``[(categoría, total_pen)]`` del mes, de mayor a menor."""
        ...

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def refresh(self, entity) -> None: ...
