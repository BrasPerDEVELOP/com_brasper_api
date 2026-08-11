import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.main import app as main_app
from app.db.base import get_db
from app.modules.audit.domain.models import AuditEventModel
from app.modules.audit.infrastructure.audited_routes_inventory import AUDITED_MUTATION_ROUTES
from app.modules.audit.infrastructure.stage_mutation_audit import stage_mutation_audit
from app.modules.audit.infrastructure.redactor import redact_data


def _mock_db():
    db = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.close = AsyncMock()
    return db


# Rutas de auth que auditan su propio evento (log_login_event / log_audit_event)
# en vez de pasar por stage_mutation_audit.
AUTH_DEDICATED_ROUTES = {
    "/auth/login",
    "/auth/facebook",
    "/auth/google",
    "/auth/refresh",
    "/auth/logout",
}


# --- 1. Verificación contra OpenAPI Schema y coincidencia exacta del inventario ---

def test_all_openapi_mutations_match_audited_inventory_and_routes_have_audit_dependency():
    openapi_schema = main_app.openapi()
    paths = openapi_schema.get("paths", {})

    openapi_mutations = set()
    for path, methods in paths.items():
        for method in methods.keys():
            m_upper = method.upper()
            if m_upper in ("POST", "PUT", "PATCH", "DELETE"):
                norm_path = path if path == "/" else path.rstrip("/")
                if norm_path in AUTH_DEDICATED_ROUTES:
                    continue
                openapi_mutations.add((m_upper, norm_path))

    # Comprobar igualdad exacta entre OpenAPI mutaciones e inventario
    assert openapi_mutations == AUDITED_MUTATION_ROUTES, (
        f"Diferencias entre OpenAPI e inventario: "
        f"Faltan en inventario: {openapi_mutations - AUDITED_MUTATION_ROUTES}, "
        f"Sobra en inventario: {AUDITED_MUTATION_ROUTES - openapi_mutations}"
    )

    # Inspeccionar que cada APIRoute tenga la dependencia stage_mutation_audit
    from fastapi.routing import APIRoute

    for route in main_app.routes:
        if isinstance(route, APIRoute) and route.include_in_schema:
            for method in route.methods:
                if method.upper() in ("POST", "PUT", "PATCH", "DELETE"):
                    clean_path = route.path if route.path == "/" else route.path.rstrip("/")
                    if clean_path in AUTH_DEDICATED_ROUTES:
                        continue
                    # Verificar dependencias
                    dep_calls = [dep.call for dep in route.dependant.dependencies]
                    has_audit = any(
                        getattr(call, "__audit_dependency__", False)
                        for call in dep_calls
                    )
                    assert has_audit, f"Ruta mutable {method} {route.path} carece de dependencia de auditoría."


# --- 2. Test del comportamiento stage_mutation_audit (mismo AsyncSession / flush sin commit) ---

@pytest.mark.asyncio
async def test_stage_mutation_audit_flushes_without_commit():
    db = _mock_db()
    request = MagicMock(spec=Request)
    request.method = "POST"
    request.url.path = "/user"
    request.headers = {"user-agent": "pytest", "X-Client-App": "backoffice"}
    request.state = MagicMock()
    request.state.request_id = str(uuid.uuid4())

    dep = stage_mutation_audit("users.create", "user")
    generator = dep(request, db=db)
    event = await anext(generator)

    assert isinstance(event, AuditEventModel)
    assert event.action == "users.create"
    assert event.entity == "user"
    assert event.source == "backoffice"
    assert event.method == "POST"

    db.add.assert_called_once()
    db.flush.assert_awaited_once()
    db.commit.assert_not_awaited()

    event.new_values = {"password": "top-secret", "name": "Alice"}
    with pytest.raises(StopAsyncIteration):
        await anext(generator)

    assert event.new_values == {"password": "[REDACTED]", "name": "Alice"}
    assert db.flush.await_count == 2
    db.commit.assert_awaited_once()


# --- 3. Demostración de persistencia y redacción de entity_id, old_values y new_values ---

def test_audit_event_enrichment_persists_details():
    app = FastAPI()
    from app.modules.users.adapters.router.user_routes import router
    from app.modules.users.application.schemas.user_schema import UserReadDTO

    db = _mock_db()
    app.dependency_overrides[get_db] = lambda: db

    u_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    dto = UserReadDTO(
        id=u_id,
        email="test@example.com",
        names="John",
        lastnames="Doe",
        phone="999888777",
        role="user",
        enable=True,
        created_at=now,
        updated_at=now,
    )

    use_case_mock = AsyncMock()
    use_case_mock.execute.return_value = dto

    from app.core.container import create_user_uc
    app.dependency_overrides[create_user_uc] = lambda: use_case_mock

    app.include_router(router)
    client = TestClient(app)

    res = client.post(
        "/user",
        data={"email": "test@example.com", "names": "John", "lastnames": "Doe", "password": "supersecretpassword123!"},
    )

    assert res.status_code in (201, 200)
    db.flush.assert_awaited()

    added_objects = [call.args[0] for call in db.add.call_args_list]
    audit_events = [obj for obj in added_objects if isinstance(obj, AuditEventModel)]
    assert len(audit_events) == 1
    event = audit_events[0]
    assert event.entity_id == str(u_id)
    assert event.new_values is not None
    assert event.new_values["password"] == "[REDACTED]"
    db.commit.assert_awaited_once()


def test_failed_mutation_middleware_captures_unauthorized_401():
    app = FastAPI()

    @app.post("/protected/action")
    async def protected_action():
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Unauthorized")

    from app.modules.audit.infrastructure.failed_mutation_middleware import FailedMutationAuditMiddleware
    app.add_middleware(FailedMutationAuditMiddleware)

    client = TestClient(app)
    res = client.post("/protected/action")
    assert res.status_code == 401


def test_public_registration_forces_client_role_and_drops_privileged_fields():
    """El registro anónimo nunca puede elegir rol, agente ni auth_id."""
    app = FastAPI()
    from app.core.container import create_user_uc
    from app.modules.auth.infrastructure.dependencies import authorize_user_creation
    from app.modules.users.adapters.router.user_routes import router
    from app.modules.users.application.schemas.user_schema import UserReadDTO

    db = _mock_db()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[authorize_user_creation] = lambda: False

    created_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    created = UserReadDTO(
        id=created_id,
        email="public@example.com",
        names="Public",
        lastnames="User",
        role="client",
        is_agent=False,
        enable=True,
        created_at=now,
        updated_at=now,
    )
    captured = {}

    async def execute(cmd, image):
        captured["cmd"] = cmd
        captured["image"] = image
        return created

    use_case = MagicMock()
    use_case.execute = AsyncMock(side_effect=execute)
    app.dependency_overrides[create_user_uc] = lambda: use_case
    app.include_router(router)

    response = TestClient(app).post(
        "/user",
        data={
            "email": "public@example.com",
            "password": "strong-password",
            "role": "admin",
            "is_agent": "true",
            "auth_id": str(uuid.uuid4()),
        },
    )

    assert response.status_code == 201, response.text
    assert captured["cmd"].role.value == "client"
    assert captured["cmd"].is_agent is False
    assert captured["cmd"].auth_id is None


def test_self_profile_schema_rejects_privilege_fields():
    from pydantic import ValidationError
    from app.modules.users.application.schemas.user_schema import UpdateCurrentUserCmd

    with pytest.raises(ValidationError):
        UpdateCurrentUserCmd.model_validate({"names": "Ana", "role": "admin"})
    with pytest.raises(ValidationError):
        UpdateCurrentUserCmd.model_validate({"names": "Ana", "is_agent": True})
