# app/modules/finance/application/use_cases.py
"""Casos de uso de tasas mensuales y egresos."""
from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from app.modules.finance.application.schemas import (
    ExpenseCategoryDTO,
    ExpenseCreateCmd,
    ExpenseDTO,
    ExpenseListDTO,
    ExpenseUpdateCmd,
    FxMonthRateDTO,
    FxRatesUpsertCmd,
)
from app.modules.finance.domain.models import Expense
from app.modules.finance.interfaces.repository import FinanceRepositoryInterface


def _expense_dto(entity: Expense) -> ExpenseDTO:
    return ExpenseDTO(
        id=entity.id,
        expense_date=entity.expense_date,
        category_id=entity.category_id,
        category_name=entity.category.name if entity.category else "",
        description=entity.description,
        amount_pen=float(entity.amount_pen),
        created_by=entity.created_by,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


class ListFxRatesUseCase:
    def __init__(self, repo: FinanceRepositoryInterface):
        self.repo = repo

    async def execute(self, year: int) -> list[FxMonthRateDTO]:
        return [FxMonthRateDTO.model_validate(r) for r in await self.repo.list_fx_rates(year)]


class UpsertFxRatesUseCase:
    def __init__(self, repo: FinanceRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: FxRatesUpsertCmd) -> list[FxMonthRateDTO]:
        seen: set[tuple[int, int, str]] = set()
        saved = []
        for item in cmd.items:
            key = (item.year, item.month, item.currency.value)
            if key in seen:
                raise ValueError(f"Tasa repetida para {item.year}-{item.month:02d} {item.currency.value}")
            seen.add(key)
            if item.currency.value == "PEN":
                raise ValueError("La tasa de soles a soles es siempre 1 y no se registra")
            saved.append(
                await self.repo.upsert_fx_rate(
                    year=item.year,
                    month=item.month,
                    currency=item.currency,
                    rate_to_pen=float(item.rate_to_pen),
                )
            )
        await self.repo.commit()
        for entity in saved:
            await self.repo.refresh(entity)
        return [FxMonthRateDTO.model_validate(e) for e in saved]


class ListExpenseCategoriesUseCase:
    def __init__(self, repo: FinanceRepositoryInterface):
        self.repo = repo

    async def execute(self) -> list[ExpenseCategoryDTO]:
        return [ExpenseCategoryDTO.model_validate(c) for c in await self.repo.list_categories()]


class ListExpensesUseCase:
    def __init__(self, repo: FinanceRepositoryInterface):
        self.repo = repo

    async def execute(
        self, *, year: int, month: Optional[int] = None, category_id: Optional[UUID] = None
    ) -> ExpenseListDTO:
        if month:
            start = date(year, month, 1)
            end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
            end = end.replace(day=1)
            date_to = date.fromordinal(end.toordinal() - 1)
        else:
            start, date_to = date(year, 1, 1), date(year, 12, 31)
        items = await self.repo.list_expenses(date_from=start, date_to=date_to, category_id=category_id)
        dtos = [_expense_dto(e) for e in items]
        return ExpenseListDTO(items=dtos, total_pen=round(sum(d.amount_pen for d in dtos), 2))


class GetExpenseUseCase:
    def __init__(self, repo: FinanceRepositoryInterface):
        self.repo = repo

    async def execute(self, expense_id: UUID) -> Optional[ExpenseDTO]:
        entity = await self.repo.get_expense(expense_id)
        return _expense_dto(entity) if entity else None


class CreateExpenseUseCase:
    def __init__(self, repo: FinanceRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: ExpenseCreateCmd, created_by: Optional[str] = None) -> ExpenseDTO:
        if not await self.repo.get_category(cmd.category_id):
            raise ValueError("Categoría de gasto no encontrada")
        entity = Expense(
            expense_date=cmd.expense_date,
            category_id=cmd.category_id,
            description=cmd.description,
            amount_pen=float(cmd.amount_pen),
            created_by=created_by,
        )
        await self.repo.add_expense(entity)
        await self.repo.commit()
        saved = await self.repo.get_expense(entity.id)
        return _expense_dto(saved or entity)


class UpdateExpenseUseCase:
    def __init__(self, repo: FinanceRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: ExpenseUpdateCmd) -> Optional[ExpenseDTO]:
        entity = await self.repo.get_expense(cmd.id)
        if not entity:
            return None
        if cmd.category_id is not None:
            if not await self.repo.get_category(cmd.category_id):
                raise ValueError("Categoría de gasto no encontrada")
            entity.category_id = cmd.category_id
        if cmd.expense_date is not None:
            entity.expense_date = cmd.expense_date
        if "description" in cmd.model_fields_set:
            entity.description = cmd.description
        if cmd.amount_pen is not None:
            entity.amount_pen = float(cmd.amount_pen)
        await self.repo.commit()
        saved = await self.repo.get_expense(cmd.id)
        return _expense_dto(saved or entity)


class DeleteExpenseUseCase:
    def __init__(self, repo: FinanceRepositoryInterface):
        self.repo = repo

    async def execute(self, expense_id: UUID) -> bool:
        entity = await self.repo.get_expense(expense_id)
        if not entity:
            return False
        entity.deleted = True
        await self.repo.commit()
        return True
