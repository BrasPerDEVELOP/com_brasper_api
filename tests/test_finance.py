"""Tasas mensuales a soles y egresos: casos de uso y contrato HTTP."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.base import get_db
from app.main import app
from app.modules.auth.domain.permissions import ALL_PERMISSIONS, DEFAULT_ROLE_PERMISSIONS
from app.modules.coin.domain.enums import Currency
from app.modules.finance.adapters.dependencies import (
    create_expense_uc,
    list_expenses_uc,
    upsert_fx_rates_uc,
)
from app.modules.finance.application.schemas import (
    ExpenseCreateCmd,
    ExpenseDTO,
    ExpenseListDTO,
    FxMonthRateDTO,
    FxRatesUpsertCmd,
)
from app.modules.finance.application.use_cases import (
    CreateExpenseUseCase,
    ListExpensesUseCase,
    UpsertFxRatesUseCase,
)

CATEGORY_ID = uuid4()


def _rate(year, month, currency, rate):
    return SimpleNamespace(
        id=uuid4(), year=year, month=month, currency=Currency(currency), rate_to_pen=rate, updated_at=None
    )


def _expense(amount, day=1, category="Planilla"):
    return SimpleNamespace(
        id=uuid4(),
        expense_date=date(2026, 7, day),
        category_id=CATEGORY_ID,
        category=SimpleNamespace(name=category),
        description=None,
        amount_pen=Decimal(str(amount)),
        created_by="tester",
        created_at=None,
        updated_at=None,
    )


class FakeRepo:
    def __init__(self):
        self.upsert_fx_rate = AsyncMock(side_effect=lambda **kw: _rate(kw["year"], kw["month"], kw["currency"].value, kw["rate_to_pen"]))
        self.commit = AsyncMock()
        self.refresh = AsyncMock()
        self.get_category = AsyncMock(return_value=SimpleNamespace(id=CATEGORY_ID, name="Planilla"))
        self.add_expense = AsyncMock(side_effect=lambda e: e)
        self.get_expense = AsyncMock(return_value=_expense(1500))
        self.list_expenses = AsyncMock(return_value=[_expense(1500), _expense(250.5, day=20)])


@pytest.mark.asyncio
async def test_upsert_rates_rejects_pen_and_duplicates():
    repo = FakeRepo()
    with pytest.raises(ValueError):
        await UpsertFxRatesUseCase(repo).execute(
            FxRatesUpsertCmd(items=[{"year": 2026, "month": 7, "currency": "PEN", "rate_to_pen": 1}])
        )
    with pytest.raises(ValueError):
        await UpsertFxRatesUseCase(repo).execute(
            FxRatesUpsertCmd(
                items=[
                    {"year": 2026, "month": 7, "currency": "brl", "rate_to_pen": 0.7},
                    {"year": 2026, "month": 7, "currency": "BRL", "rate_to_pen": 0.71},
                ]
            )
        )
    repo.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_upsert_rates_saves_each_item_once():
    repo = FakeRepo()
    result = await UpsertFxRatesUseCase(repo).execute(
        FxRatesUpsertCmd(
            items=[
                {"year": 2026, "month": 7, "currency": "brl", "rate_to_pen": "0.70"},
                {"year": 2026, "month": 7, "currency": "USD", "rate_to_pen": 3.5},
            ]
        )
    )
    assert [r.currency for r in result] == [Currency.brl, Currency.usd]
    assert repo.upsert_fx_rate.await_count == 2
    repo.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_expenses_sums_month_total():
    repo = FakeRepo()
    result = await ListExpensesUseCase(repo).execute(year=2026, month=7)
    assert isinstance(result, ExpenseListDTO)
    assert result.total_pen == 1750.5
    repo.list_expenses.assert_awaited_once_with(
        date_from=date(2026, 7, 1), date_to=date(2026, 7, 31), category_id=None
    )


@pytest.mark.asyncio
async def test_create_expense_requires_existing_category():
    repo = FakeRepo()
    repo.get_category = AsyncMock(return_value=None)
    with pytest.raises(ValueError):
        await CreateExpenseUseCase(repo).execute(
            ExpenseCreateCmd(expense_date=date(2026, 7, 1), category_id=uuid4(), amount_pen=10)
        )


def test_expense_cmd_rejects_non_positive_amount():
    with pytest.raises(ValueError):
        ExpenseCreateCmd(expense_date=date(2026, 7, 1), category_id=uuid4(), amount_pen=0)


def test_finance_endpoints_contract():
    fx_uc = AsyncMock(spec=UpsertFxRatesUseCase)
    fx_uc.execute = AsyncMock(
        return_value=[FxMonthRateDTO(id=uuid4(), year=2026, month=7, currency="BRL", rate_to_pen=0.7)]
    )
    list_uc = AsyncMock(spec=ListExpensesUseCase)
    list_uc.execute = AsyncMock(
        return_value=ExpenseListDTO(
            items=[
                ExpenseDTO(
                    id=uuid4(),
                    expense_date=date(2026, 7, 3),
                    category_id=CATEGORY_ID,
                    category_name="Planilla",
                    amount_pen=1500.0,
                )
            ],
            total_pen=1500.0,
        )
    )
    create_uc = AsyncMock(spec=CreateExpenseUseCase)
    create_uc.execute = AsyncMock(
        return_value=ExpenseDTO(
            id=uuid4(),
            expense_date=date(2026, 7, 3),
            category_id=CATEGORY_ID,
            category_name="Planilla",
            amount_pen=99.9,
        )
    )
    # La auditoría de mutaciones usa la sesión de get_db (add + flush); se simula.
    db_mock = MagicMock()
    db_mock.flush = AsyncMock()
    db_mock.commit = AsyncMock()
    db_mock.rollback = AsyncMock()
    app.dependency_overrides[get_db] = lambda: db_mock
    app.dependency_overrides[upsert_fx_rates_uc] = lambda: fx_uc
    app.dependency_overrides[list_expenses_uc] = lambda: list_uc
    app.dependency_overrides[create_expense_uc] = lambda: create_uc
    client = TestClient(app)
    try:
        fx = client.put(
            "/finance/fx-rates",
            json={"items": [{"year": 2026, "month": 7, "currency": "BRL", "rate_to_pen": 0.7}]},
        )
        listed = client.get("/finance/expenses", params={"year": 2026, "month": 7})
        created = client.post(
            "/finance/expenses",
            json={"expense_date": "2026-07-03", "category_id": str(CATEGORY_ID), "amount_pen": 99.9},
        )
        bad = client.post(
            "/finance/expenses",
            json={"expense_date": "2026-07-03", "category_id": str(CATEGORY_ID), "amount_pen": -1},
        )
    finally:
        for dep in (get_db, upsert_fx_rates_uc, list_expenses_uc, create_expense_uc):
            app.dependency_overrides.pop(dep, None)

    assert fx.status_code == 200 and fx.json()[0]["currency"] == "BRL"
    assert listed.status_code == 200 and listed.json()["total_pen"] == 1500.0
    assert created.status_code == 201 and created.json()["category_name"] == "Planilla"
    assert bad.status_code == 422


def test_finance_permissions_are_catalogued():
    for key in ("fx_rates.view", "fx_rates.update", "expenses.view", "expenses.create", "expenses.update", "expenses.delete"):
        assert key in ALL_PERMISSIONS
        assert key in DEFAULT_ROLE_PERMISSIONS["accounting"]
        assert key not in DEFAULT_ROLE_PERMISSIONS["sales"]
