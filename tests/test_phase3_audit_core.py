import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.db.base import get_db
from app.modules.audit.domain.models import AuditEventModel, LoginEventModel
from app.modules.audit.infrastructure.audit_repository import AuditRepository
from app.modules.audit.infrastructure.redactor import redact_data, redact_value


def _mock_db() -> MagicMock:
    db = MagicMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


# --- 1. Pruebas de coincidencia de Modelos vs Migración 065 y Timezone Aware ---

def test_audit_models_schema_and_timezone_aware():
    # Validar AuditEventModel
    assert AuditEventModel.__tablename__ == "audit_event"
    assert AuditEventModel.__table_args__[-1]["schema"] == "audit"

    # Verificar indices y constraints explícitos
    table_args = AuditEventModel.__table_args__
    check_constraints = [arg for arg in table_args if hasattr(arg, "name") and arg.name == "ck_audit_event_source"]
    assert len(check_constraints) == 1

    # Verificar UTC aware en AuditRepository
    from app.modules.audit.infrastructure.audit_repository import _utc_now
    now = _utc_now()
    assert now.tzinfo is not None
    assert now.tzinfo == timezone.utc


# --- 2. Pruebas de Censura y Redacción (Redactor) ---

def test_redactor_censors_sensitive_keys_recursively():
    sensitive_payload = {
        "username": "johndoe",
        "password": "supersecretpassword",
        "token": "bearer-xyz-123",
        "nested": {
            "current_password": "oldpassword",
            "new_password": "newpassword",
            "authorization": "Bearer token",
            "recovery_code": "123456",
            "cookie": "session=abc",
        },
        "list_data": [
            {"secret": "my-secret-key"},
            {"public": "visible_value"},
        ],
        "send_vouchers": ["transaction_vouchers/send_private.pdf"],
        "banner_es": "home_banner/banner_es_private.webp",
    }

    redacted = redact_data(sensitive_payload)

    assert redacted["username"] == "johndoe"
    assert redacted["password"] == "[REDACTED]"
    assert redacted["token"] == "[REDACTED]"
    assert redacted["nested"]["current_password"] == "[REDACTED]"
    assert redacted["nested"]["new_password"] == "[REDACTED]"
    assert redacted["nested"]["authorization"] == "[REDACTED]"
    assert redacted["nested"]["recovery_code"] == "[REDACTED]"
    assert redacted["nested"]["cookie"] == "[REDACTED]"
    assert redacted["list_data"][0]["secret"] == "[REDACTED]"
    assert redacted["list_data"][1]["public"] == "visible_value"
    assert redacted["send_vouchers"] == "[REDACTED]"
    assert redacted["banner_es"] == "[REDACTED]"


def test_redactor_masks_financial_and_document_numbers():
    financial_payload = {
        "cci": "00219100000000000012",
        "cpf": "12345678901",
        "document_number": "736452819",
        "normal_id": "123",
    }

    redacted = redact_data(financial_payload)

    assert redacted["cci"] == "002***012"
    assert redacted["cpf"] == "123***901"
    assert redacted["document_number"] == "736***819"
    assert redacted["normal_id"] == "123"


# --- 3. Pruebas de AuditRepository Append-Only ---

@pytest.mark.asyncio
async def test_audit_repository_log_audit_event_flushes_without_commit():
    db = _mock_db()
    repo = AuditRepository(db)
    request_id = uuid.uuid4()
    actor_id = uuid.uuid4()

    event = await repo.log_audit_event(
        action="user.update",
        entity="user",
        request_id=request_id,
        actor_user_id=actor_id,
        entity_id="123",
        old_values={"password": "old_pass", "name": "Old Name"},
        new_values={"password": "new_pass", "name": "New Name"},
        source="backoffice",
    )

    assert isinstance(event, AuditEventModel)
    assert event.action == "user.update"
    assert event.old_values["password"] == "[REDACTED]"
    assert event.old_values["name"] == "Old Name"
    assert event.new_values["password"] == "[REDACTED]"
    assert event.new_values["name"] == "New Name"

    db.add.assert_called_once()
    db.flush.assert_awaited_once()
    db.commit.assert_not_called()  # Append-only: persisten en la misma transacción del caso de uso


@pytest.mark.asyncio
async def test_audit_repository_log_login_event():
    db = _mock_db()
    repo = AuditRepository(db)
    request_id = uuid.uuid4()
    user_id = uuid.uuid4()

    login_event = await repo.log_login_event(
        success=True,
        request_id=request_id,
        attempted_username="admin@brasper.com",
        user_id=user_id,
        ip_address="190.235.12.4",
        user_agent="Mozilla/5.0",
        source="backoffice",
    )

    assert isinstance(login_event, LoginEventModel)
    assert login_event.success is True
    assert login_event.attempted_username == "admin@brasper.com"
    assert login_event.ip_address == "190.235.12.4"
    db.add.assert_called_once()
    db.flush.assert_awaited_once()


# --- 4. Integración de Eventos de Logout, Login y Single-Transaction ---

def test_logout_creates_audit_event_and_single_commit():
    app = FastAPI()
    from app.modules.auth.adapters.router.auth_routes import router

    db = _mock_db()
    db.execute.return_value.scalar_one_or_none.return_value = None

    app.dependency_overrides[get_db] = lambda: db
    app.include_router(router)
    client = TestClient(app)

    res = client.post("/auth/logout")
    assert res.status_code == 200

    # Verificar que solo se ejecutó UN commit en todo el handler de logout
    assert db.commit.await_count == 1

    # Verificar que se agregó el evento de auditoría a la sesión de BD
    added_objects = [call.args[0] for call in db.add.call_args_list]
    audit_events = [obj for obj in added_objects if isinstance(obj, AuditEventModel)]
    assert len(audit_events) == 1
    assert audit_events[0].action == "auth.logout"
    assert audit_events[0].entity == "auth_session"
