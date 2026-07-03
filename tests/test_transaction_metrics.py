"""Test del endpoint de métricas del dashboard."""
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.transactions.adapters.dependencies.transaction_dependencies import (
    get_transaction_metrics_uc,
)
from app.modules.transactions.application.schemas import TransactionMetricsDTO
from app.modules.transactions.application.use_cases import GetTransactionMetricsUseCase


@pytest.fixture
def metrics_client():
    uc = AsyncMock(spec=GetTransactionMetricsUseCase)
    uc.execute = AsyncMock(
        return_value=TransactionMetricsDTO(
            total=42,
            by_status={"verification": 30, "completed": 10, "failed": 2},
            volume_origin=15000.5,
            volume_destination=14250.0,
            last_7_days=7,
        )
    )
    app.dependency_overrides[get_transaction_metrics_uc] = lambda: uc
    yield TestClient(app)
    app.dependency_overrides.pop(get_transaction_metrics_uc, None)


def test_metrics_endpoint_returns_aggregates(metrics_client):
    res = metrics_client.get("/transactions/metrics")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 42
    assert body["by_status"]["verification"] == 30
    assert body["volume_origin"] == 15000.5
    assert body["volume_destination"] == 14250.0
    assert body["last_7_days"] == 7


def test_metrics_route_not_shadowed_by_id_route(metrics_client):
    # "/transactions/metrics" no debe interpretarse como un id (UUID) → no 422.
    res = metrics_client.get("/transactions/metrics")
    assert res.status_code != 422
