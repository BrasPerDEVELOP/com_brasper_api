"""Contrato del panel gerencial (``GET /metrics/management``)."""
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from datetime import date

from app.modules.auth.domain.permissions import ALL_PERMISSIONS, DEFAULT_ROLE_PERMISSIONS
from app.modules.coin.domain.enums import Currency
from app.modules.metrics.adapters.dependencies import get_management_dashboard_uc
from app.modules.metrics.application.schemas import ManagementDashboardDTO
from app.modules.metrics.application.use_cases import GetManagementDashboardUseCase
from app.modules.metrics.infrastructure.management_repository import _empty_month, apply_fx


def _month(period_start: str, **overrides) -> dict:
    base = {
        "period_start": period_start,
        "envios_count": 0,
        "envios_by_currency": {"PEN": 0, "BRL": 0, "USD": 0},
        "envios_by_company": {},
        "active_clients": 0,
        "new_clients": 0,
        "volume_origin": {"PEN": 0.0, "BRL": 0.0, "USD": 0.0},
        "commission_origin": {"PEN": 0.0, "BRL": 0.0, "USD": 0.0},
        "volume_pen_by_currency": {"PEN": 0.0, "BRL": 0.0, "USD": 0.0},
        "volume_pen_total": 0.0,
        "revenue_pen": 0.0,
        "expenses_pen": 0.0,
        "net_pen": 0.0,
    }
    base.update(overrides)
    return base


PAYLOAD = {
    "range": {
        "year": 2026,
        "date_from": "2026-01-01",
        "date_to": "2026-12-31",
        "corridor": "Todos",
        "currency": None,
        "company": None,
        "status": None,
    },
    "months": [
        _month(
            "2026-01-01",
            envios_count=1305,
            envios_by_currency={"PEN": 594, "BRL": 636, "USD": 75},
            envios_by_company={"BRASPER": 294, "INGENITECH": 375, "Brasper Brasil": 636},
            active_clients=505,
            new_clients=84,
            volume_origin={"PEN": 646000.0, "BRL": 1536000.0, "USD": 62540.0},
        )
    ]
    + [_month(f"2026-{m:02d}-01") for m in range(2, 13)],
    "previous_month": _month("2025-12-01", active_clients=500),
    "totals": {
        "envios_count": 1305,
        "active_clients": 505,
        "new_clients": 84,
        "volume_origin": {"PEN": 646000.0, "BRL": 1536000.0, "USD": 62540.0},
    },
    "companies": ["BRASPER", "Brasper Brasil", "INGENITECH"],
    "top_clients": {
        "month": 1,
        "items": [{"user_id": "315b2852-f4d7-4b84-bdd2-b14d77f1371b", "name": "Ana", "envios_count": 21}],
    },
}


class FakeRepo:
    def __init__(self):
        self.dashboard = AsyncMock(return_value=PAYLOAD)


@pytest.mark.asyncio
async def test_use_case_normalizes_filters():
    repo = FakeRepo()
    result = await GetManagementDashboardUseCase(repo).execute(
        year=2026,
        corridor="pen_brl",
        currency="pen",
        company="  BRASPER ",
        status="",
        top_month=7,
        top_limit=500,
    )
    assert isinstance(result, ManagementDashboardDTO)
    repo.dashboard.assert_awaited_once_with(
        year=2026,
        corridor="PEN_BRL",
        currency=Currency.pen,
        company="BRASPER",
        status=None,
        top_month=7,
        top_limit=50,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs",
    [
        {"year": 1999},
        {"corridor": "PEN_USD"},
        {"currency": "EUR"},
        {"top_month": 13},
    ],
)
async def test_use_case_rejects_invalid_filters(kwargs):
    with pytest.raises(HTTPException) as exc:
        await GetManagementDashboardUseCase(FakeRepo()).execute(**kwargs)
    assert exc.value.status_code == 422


def test_endpoint_returns_contract():
    use_case = AsyncMock(spec=GetManagementDashboardUseCase)
    use_case.execute = AsyncMock(return_value=ManagementDashboardDTO(**PAYLOAD))
    app.dependency_overrides[get_management_dashboard_uc] = lambda: use_case
    try:
        response = TestClient(app).get(
            "/metrics/management", params={"year": 2026, "top_month": 1}
        )
    finally:
        app.dependency_overrides.pop(get_management_dashboard_uc, None)

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["months"]) == 12
    assert body["previous_month"]["period_start"] == "2025-12-01"
    assert body["months"][0]["envios_by_company"]["Brasper Brasil"] == 636
    assert body["top_clients"]["items"][0]["envios_count"] == 21
    assert body["companies"] == ["BRASPER", "Brasper Brasil", "INGENITECH"]


def test_management_permission_is_catalogued():
    assert "management.view" in ALL_PERMISSIONS
    assert "management.view" in DEFAULT_ROLE_PERMISSIONS["accounting"]
    assert "management.view" not in DEFAULT_ROLE_PERMISSIONS["sales"]


def test_apply_fx_converts_to_pen_and_reports_missing_rates():
    month = _empty_month(date(2026, 7, 1))
    month["volume_origin"] = {"PEN": 1000.0, "BRL": 200.0, "USD": 50.0}
    month["commission_origin"] = {"PEN": 30.0, "BRL": 6.0, "USD": 1.5}
    month["expenses_pen"] = 100.0

    missing = apply_fx(month, 2026, 7, {(2026, 7, "BRL"): 0.7, (2026, 7, "USD"): 3.5})
    assert missing == []
    assert month["volume_pen_by_currency"] == {"PEN": 1000.0, "BRL": 140.0, "USD": 175.0}
    assert month["volume_pen_total"] == 1315.0
    assert month["revenue_pen"] == round(30 + 6 * 0.7 + 1.5 * 3.5, 2)
    assert month["net_pen"] == round(month["revenue_pen"] - 100.0, 2)

    # Sin tasa de USD: el mes queda sin total en soles y se reporta la moneda.
    month = _empty_month(date(2026, 8, 1))
    month["volume_origin"] = {"PEN": 10.0, "BRL": 0.0, "USD": 5.0}
    assert apply_fx(month, 2026, 8, {(2026, 8, "BRL"): 0.7}) == ["USD"]
    assert month["volume_pen_total"] is None
    assert month["volume_pen_by_currency"]["USD"] is None
    assert month["volume_pen_by_currency"]["BRL"] == 0.0
