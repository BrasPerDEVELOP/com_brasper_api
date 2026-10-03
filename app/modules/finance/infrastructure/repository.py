# app/modules/finance/infrastructure/repository.py
from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.coin.domain.enums import Currency
from app.modules.finance.domain.models import Expense, ExpenseCategory, FxMonthRate
from app.modules.finance.interfaces.repository import FinanceRepositoryInterface


class SQLAlchemyFinanceRepository(FinanceRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.session = db

    # --- Tasas mensuales -------------------------------------------------
    async def list_fx_rates(self, year: int) -> list[FxMonthRate]:
        stmt = (
            select(FxMonthRate)
            .where(FxMonthRate.deleted.is_(False), FxMonthRate.year == year)
            .order_by(FxMonthRate.month, FxMonthRate.currency)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def fx_rates_map(self, years: list[int]) -> dict[tuple[int, int, str], float]:
        if not years:
            return {}
        stmt = select(FxMonthRate).where(
            FxMonthRate.deleted.is_(False), FxMonthRate.year.in_(years)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return {
            (row.year, row.month, row.currency.value if hasattr(row.currency, "value") else str(row.currency)): float(
                row.rate_to_pen
            )
            for row in rows
        }

    async def upsert_fx_rate(
        self, *, year: int, month: int, currency: Currency, rate_to_pen: float
    ) -> FxMonthRate:
        stmt = select(FxMonthRate).where(
            FxMonthRate.year == year,
            FxMonthRate.month == month,
            FxMonthRate.currency == currency,
        )
        entity = (await self.session.execute(stmt)).scalar_one_or_none()
        if entity is None:
            entity = FxMonthRate(year=year, month=month, currency=currency, rate_to_pen=rate_to_pen)
            self.session.add(entity)
        else:
            entity.rate_to_pen = rate_to_pen
            entity.deleted = False
        return entity

    # --- Categorías ------------------------------------------------------
    async def list_categories(self) -> list[ExpenseCategory]:
        stmt = (
            select(ExpenseCategory)
            .where(ExpenseCategory.deleted.is_(False))
            .order_by(ExpenseCategory.position, ExpenseCategory.name)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_category(self, category_id: UUID) -> Optional[ExpenseCategory]:
        stmt = select(ExpenseCategory).where(
            ExpenseCategory.id == category_id, ExpenseCategory.deleted.is_(False)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    # --- Egresos ---------------------------------------------------------
    async def list_expenses(
        self, *, date_from: date, date_to: date, category_id: Optional[UUID] = None
    ) -> list[Expense]:
        stmt = select(Expense).where(
            Expense.deleted.is_(False),
            Expense.expense_date >= date_from,
            Expense.expense_date <= date_to,
        )
        if category_id is not None:
            stmt = stmt.where(Expense.category_id == category_id)
        stmt = stmt.order_by(Expense.expense_date.desc(), Expense.created_at.desc())
        return list((await self.session.execute(stmt)).unique().scalars().all())

    async def get_expense(self, expense_id: UUID) -> Optional[Expense]:
        stmt = select(Expense).where(Expense.id == expense_id, Expense.deleted.is_(False))
        return (await self.session.execute(stmt)).unique().scalar_one_or_none()

    async def add_expense(self, entity: Expense) -> Expense:
        self.session.add(entity)
        return entity

    async def monthly_expenses(self, year: int) -> dict[int, float]:
        month = extract("month", Expense.expense_date)
        stmt = (
            select(month.label("month"), func.coalesce(func.sum(Expense.amount_pen), 0))
            .where(Expense.deleted.is_(False), extract("year", Expense.expense_date) == year)
            .group_by(month)
        )
        return {int(row[0]): float(row[1] or 0) for row in (await self.session.execute(stmt)).all()}

    async def expenses_by_category(self, year: int, month: int) -> list[tuple[str, float]]:
        total = func.coalesce(func.sum(Expense.amount_pen), 0)
        stmt = (
            select(ExpenseCategory.name, total)
            .join(ExpenseCategory, ExpenseCategory.id == Expense.category_id)
            .where(
                Expense.deleted.is_(False),
                extract("year", Expense.expense_date) == year,
                extract("month", Expense.expense_date) == month,
            )
            .group_by(ExpenseCategory.name)
            .order_by(total.desc(), ExpenseCategory.name)
        )
        return [(str(row[0]), float(row[1] or 0)) for row in (await self.session.execute(stmt)).all()]

    async def commit(self) -> None:
        await self.session.commit()

    async def refresh(self, entity) -> None:
        await self.session.refresh(entity)
