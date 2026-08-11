"""Contrato de lectura de auditoría: permiso, filtros y detalle sensible."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.db.base import get_db
from app.modules.audit.adapters.router.audit_routes import router
from app.modules.audit.domain.models import AuditEventModel
from app.modules.auth.infrastructure.dependencies import get_current_user_permissions


def _event() -> AuditEventModel:
    return AuditEventModel(
        id=uuid4(),
        actor_user_id=uuid4(),
        actor_username="admin@example.com",
        actor_role="admin",
        action="users.delete",
        entity="user",
        entity_id=str(uuid4()),
        description="Usuario eliminado",
        old_values={"email": "masked@example.com"},
        new_values=None,
        source="backoffice",
        ip_address="203.0.113.10",
        user_agent="Sensitive Browser Details",
        method="DELETE",
        path="/user/example",
        status_code=204,
        request_id=uuid4(),
        success=True,
        meta_data={"reason": "requested"},
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def audit_client():
    settings = get_settings()
    previous = settings.AUTH_REQUIRED
    settings.AUTH_REQUIRED = True

    event = _event()
    db = MagicMock()
    db.scalar = AsyncMock(return_value=1)
    result = MagicMock()
    result.scalars.return_value.all.return_value = [event]
    db.execute = AsyncMock(return_value=result)
    db.get = AsyncMock(return_value=event)

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    permissions = {"value": ["audit.view"]}
    app.dependency_overrides[get_current_user_permissions] = lambda: permissions["value"]

    try:
        yield TestClient(app), permissions, event, db
    finally:
        settings.AUTH_REQUIRED = previous


def test_audit_routes_require_audit_view(audit_client):
    client, permissions, event, _db = audit_client
    permissions["value"] = []

    assert client.get("/audit/events").status_code == 403
    assert client.get(f"/audit/events/{event.id}").status_code == 403
    assert client.get("/audit/logins").status_code == 403


def test_event_list_is_lightweight_and_detail_contains_snapshots(audit_client):
    client, _permissions, event, _db = audit_client

    response = client.get(
        "/audit/events",
        params={"ip_address": "203.0.113.10", "source": "backoffice", "limit": 25},
    )
    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert item["id"] == str(event.id)
    assert "old_values" not in item
    assert "new_values" not in item
    assert "user_agent" not in item
    assert "metadata" not in item

    detail = client.get(f"/audit/events/{event.id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["old_values"] == {"email": "masked@example.com"}
    assert detail.json()["user_agent"] == "Sensitive Browser Details"


def test_audit_filters_reject_unknown_source(audit_client):
    client, _permissions, _event, _db = audit_client
    assert client.get("/audit/events", params={"source": "untrusted"}).status_code == 422
