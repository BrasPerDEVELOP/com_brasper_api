# app/modules/finance/adapters/dependencies.py
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.modules.finance.application.use_cases import (
    CreateExpenseUseCase,
    DeleteExpenseUseCase,
    GetExpenseUseCase,
    ListExpenseCategoriesUseCase,
    ListExpensesUseCase,
    ListFxRatesUseCase,
    UpdateExpenseUseCase,
    UpsertFxRatesUseCase,
)
from app.modules.finance.infrastructure.repository import SQLAlchemyFinanceRepository
from app.modules.finance.interfaces.repository import FinanceRepositoryInterface


def get_finance_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FinanceRepositoryInterface:
    return SQLAlchemyFinanceRepository(db)


RepoDep = Annotated[FinanceRepositoryInterface, Depends(get_finance_repository)]


def list_fx_rates_uc(repo: RepoDep) -> ListFxRatesUseCase:
    return ListFxRatesUseCase(repo)


def upsert_fx_rates_uc(repo: RepoDep) -> UpsertFxRatesUseCase:
    return UpsertFxRatesUseCase(repo)


def list_categories_uc(repo: RepoDep) -> ListExpenseCategoriesUseCase:
    return ListExpenseCategoriesUseCase(repo)


def list_expenses_uc(repo: RepoDep) -> ListExpensesUseCase:
    return ListExpensesUseCase(repo)


def get_expense_uc(repo: RepoDep) -> GetExpenseUseCase:
    return GetExpenseUseCase(repo)


def create_expense_uc(repo: RepoDep) -> CreateExpenseUseCase:
    return CreateExpenseUseCase(repo)


def update_expense_uc(repo: RepoDep) -> UpdateExpenseUseCase:
    return UpdateExpenseUseCase(repo)


def delete_expense_uc(repo: RepoDep) -> DeleteExpenseUseCase:
    return DeleteExpenseUseCase(repo)


ListFxRatesUseCaseDep = Annotated[ListFxRatesUseCase, Depends(list_fx_rates_uc)]
UpsertFxRatesUseCaseDep = Annotated[UpsertFxRatesUseCase, Depends(upsert_fx_rates_uc)]
ListExpenseCategoriesUseCaseDep = Annotated[ListExpenseCategoriesUseCase, Depends(list_categories_uc)]
ListExpensesUseCaseDep = Annotated[ListExpensesUseCase, Depends(list_expenses_uc)]
GetExpenseUseCaseDep = Annotated[GetExpenseUseCase, Depends(get_expense_uc)]
CreateExpenseUseCaseDep = Annotated[CreateExpenseUseCase, Depends(create_expense_uc)]
UpdateExpenseUseCaseDep = Annotated[UpdateExpenseUseCase, Depends(update_expense_uc)]
DeleteExpenseUseCaseDep = Annotated[DeleteExpenseUseCase, Depends(delete_expense_uc)]
