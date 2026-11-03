"""Regressions for @usernames crossing HTTP validation and user persistence."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.modules.brasper.application.ai_schemas import AIClientUpsertCmd
from app.modules.brasper.application.ai_service import BrasperAIService
from app.modules.users.application.schemas.user_schema import (
    UpdateCurrentUserCmd, UserCreateCmd, UserUpdateCmd,
    UserReadDTO, UserReadGeneralDTO,
)
from app.modules.users.application.use_cases.user_use_cases import (
    CreateUserUseCase, UpdateUserUseCase,
)
from app.modules.users.domain.models import User


@pytest.mark.parametrize("cls", [UserCreateCmd, UserUpdateCmd, UpdateCurrentUserCmd])
@pytest.mark.parametrize("raw,expected", [
    (" @evymur2 ", "@evymur2"), ("001234567", "001234567"),
    (987654321, "987654321"), ("987654321", "987654321"),
    (None, None), ("", None), ("   ", None),
])
def test_commands_preserve_text_and_legacy_numbers(cls, raw, expected):
    values = {"phone": raw}
    if cls is UserUpdateCmd:
        values["id"] = uuid4()
    assert cls(**values).phone == expected


@pytest.mark.parametrize("raw", [True, 123.5, {}, [], "@" + "a" * 100])
def test_phone_rejects_invalid_types_and_excessive_length(raw):
    with pytest.raises(ValidationError):
        UserCreateCmd(phone=raw)


@pytest.fixture
def phone_client():
    # Exercise FastAPI's actual form dependency: the old int annotation failed
    # before from_form or the use case could even run.
    app = FastAPI()

    @app.post("/user")
    def create(form=Depends(UserCreateCmd.from_form)):
        return form[0].model_dump(mode="json", exclude_unset=True)

    @app.put("/user")
    def update(form=Depends(UserUpdateCmd.from_form)):
        return form[0].model_dump(mode="json", exclude_unset=True)

    @app.put("/auth/me")
    def profile(cmd: UpdateCurrentUserCmd):
        return cmd.model_dump(mode="json", exclude_unset=True)

    return TestClient(app)


@pytest.mark.parametrize("method", ["post", "put"])
@pytest.mark.parametrize("phone", ["@evymur2", "001234567", "987654321"])
@pytest.mark.parametrize("code", [None, "+51"])
def test_multipart_accepts_phone_with_or_without_country(phone_client, method, phone, code):
    fields = {"id": str(uuid4()), "phone": phone}
    if code:
        fields["code_phone"] = code
    response = phone_client.request(method, "/user", files={k: (None, v) for k, v in fields.items()})
    assert response.status_code == 200, response.text
    assert response.json()["phone"] == phone


def test_http_length_limit_and_optional_profile_phone(phone_client):
    response = phone_client.post("/user", files={"phone": (None, "a" * 101)})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "phone"]
    assert "phone" not in phone_client.put("/user", data={"id": str(uuid4())}).json()
    for raw, expected in [("@evymur2", "@evymur2"), (987654321, "987654321"), (None, None)]:
        response = phone_client.put("/auth/me", json={"phone": raw})
        assert response.status_code == 200
        assert response.json()["phone"] == expected


@pytest.mark.parametrize("raw,expected", [
    ("@evymur2", "@evymur2"), (987654321, 987654321),
    ("987654321", 987654321), ("001234567", "001234567"), (None, None),
])
def test_read_dtos_serialize_text_and_legacy_records(raw, expected):
    user = User(id=uuid4(), phone=raw, created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc), identifications=[],
                permissions_granted=[], permissions_revoked=[])
    for dto in (UserReadDTO, UserReadGeneralDTO):
        assert dto.model_validate(user).model_dump()["phone"] == expected


async def test_create_and_update_persist_username():
    saved = User(id=uuid4(), created_at=datetime.now(timezone.utc),
                 updated_at=datetime.now(timezone.utc), identifications=[],
                 permissions_granted=[], permissions_revoked=[])
    uow = MagicMock()

    async def add(user):
        saved.phone = user.phone
        return saved

    uow.user_repository.add = AsyncMock(side_effect=add)
    uow.user_repository.get = AsyncMock(return_value=saved)
    uow.user_repository.update = AsyncMock(side_effect=lambda user: user)
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    created = await CreateUserUseCase(uow, AsyncMock()).execute(UserCreateCmd(phone="@evymur2"), None)
    assert created.phone == saved.phone == "@evymur2"
    update = UpdateUserUseCase(uow)
    await update.execute(UserUpdateCmd(id=saved.id, names="Nuevo"))
    assert saved.phone == "@evymur2"
    updated = await update.execute(UserUpdateCmd(id=saved.id, phone="001234567"))
    assert updated.phone == saved.phone == "001234567"
    await update.execute(UserUpdateCmd(id=saved.id, phone=None))
    assert saved.phone is None


@pytest.mark.parametrize("operation", ["lookup", "history", "status", "upsert_lookup"])
async def test_ai_numeric_phone_queries_bind_text(operation):
    session = MagicMock()
    session.scalars = AsyncMock(return_value=SimpleNamespace(first=lambda: None, all=lambda: []))
    service = BrasperAIService(session)
    if operation == "lookup":
        await service.lookup_client(code_phone="+51", phone=987654321, full_name=None)
    elif operation == "history":
        await service.client_history(uuid4(), code_phone="+51", phone=987654321)
    elif operation == "status":
        await service.operation_status(uuid4(), code_phone="+51", phone=987654321)
    else:
        await service._find_by_phone(AIClientUpsertCmd(
            names="Prueba", lastnames="Prueba", document_type="dni",
            document_number="12345678", code_phone="+51", phone=987654321,
        ))
    params = session.scalars.call_args.args[0].compile().params
    assert params["phone_1"] == "987654321"
