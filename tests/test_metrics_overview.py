"""Contrato del panel de métricas unificado."""
from datetime import date
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.modules.metrics.adapters.dependencies import get_metrics_overview_uc
from app.modules.metrics.application.schemas import MetricsOverviewDTO
from app.modules.metrics.application.use_cases import GetMetricsOverviewUseCase


OVERVIEW_PAYLOAD = {
    "range": {
        "date_from": "2026-08-01",
        "date_to": "2026-08-27",
        "origin_currency": None,
        "destination_currency": None,
        "corridor": "Todos",
        "granularity": "week",
    },
    "series": [
        {
            "period_start": "2026-08-03",
            "envios_count": 12,
            "clientes_nuevos": 3,
            "volume_origin": {"PEN": 1800.0, "BRL": 900.0, "USD": 100.0},
        }
    ],
    "totals": {
        "envios_count": 12,
        "clientes_nuevos": 3,
        "active_agents": 2,
        "volume_origin": {"PEN": 1800.0, "BRL": 900.0, "USD": 100.0},
    },
    "breakdown_by_status": [{"key": "completed", "count": 9}],
    "breakdown_by_tag": [
        {
            "tag_id": "74360c1b-8101-429c-b6fd-47aa2f5ac47c",
            "label": "Cliente nuevo",
            "color": "emerald",
            "active": True,
            "count": 3,
        }
    ],
    "breakdown_by_agent": [
        {
            "agent_id": None,
            "agent_name": "Sin asesor",
            "envios_count": 2,
            "volume_origin": {"PEN": 100.0, "BRL": 0.0, "USD": 0.0},
        }
    ],
}


class FakeMetricsRepository:
    def __init__(self):
        self.overview_metrics = AsyncMock(return_value=OVERVIEW_PAYLOAD)

    async def period_metrics(self, **kwargs):  # pragma: no cover - puerto legado
        raise NotImplementedError


@pytest.mark.asyncio
async def test_overview_use_case_normalizes_filters_and_ids():
    repo = FakeMetricsRepository()
    use_case = GetMetricsOverviewUseCase(repo)
    agent_id = "315b2852-f4d7-4b84-bdd2-b14d77f1371b"
    tag_id = "74360c1b-8101-429c-b6fd-47aa2f5ac47c"

    result = await use_case.execute(
        corridor="pen_brl",
        date_from="2026-08-27",
        date_to="2026-08-01",
        granularity="week",
        status="completed",
        agent_id=agent_id,
        tag_ids=[tag_id, tag_id],
    )

    assert isinstance(result, MetricsOverviewDTO)
    repo.overview_metrics.assert_awaited_once_with(
        corridor="PEN_BRL",
        date_from=date(2026, 8, 1),
        date_to=date(2026, 8, 27),
        granularity="week",
        status="completed",
        agent_id=UUID(agent_id),
        tag_ids=[UUID(tag_id)],
    )


@pytest.mark.asyncio
async def test_overview_use_case_rejects_unknown_corridor():
    use_case = GetMetricsOverviewUseCase(FakeMetricsRepository())
    with pytest.raises(HTTPException) as exc:
        await use_case.execute(corridor="PEN_USD")
    assert exc.value.status_code == 422


def test_overview_endpoint_returns_all_coordinated_blocks():
    use_case = AsyncMock(spec=GetMetricsOverviewUseCase)
    use_case.execute = AsyncMock(return_value=MetricsOverviewDTO(**OVERVIEW_PAYLOAD))
    app.dependency_overrides[get_metrics_overview_uc] = lambda: use_case
    try:
        response = TestClient(app).get(
            "/metrics/overview",
            params=[
                ("corridor", "all"),
                ("date_from", "2026-08-01"),
                ("date_to", "2026-08-27"),
                ("tag_ids", "74360c1b-8101-429c-b6fd-47aa2f5ac47c"),
            ],
        )
    finally:
        app.dependency_overrides.pop(get_metrics_overview_uc, None)

    assert response.status_code == 200
    body = response.json()
    assert body["totals"]["envios_count"] == 12
    assert body["breakdown_by_agent"][0]["agent_name"] == "Sin asesor"
    assert body["breakdown_by_tag"][0]["label"] == "Cliente nuevo"
    use_case.execute.assert_awaited_once()
