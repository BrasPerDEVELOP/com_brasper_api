"""Señales no sensibles de completitud usadas por la tabla de transacciones."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.modules.users.application.use_cases.user_use_cases import ListUserNameUseCase
from app.modules.users.application.schemas.user_schema import UserUpdateCmd
from app.modules.users.adapters.router import user_routes


def test_name_list_exposes_only_email_and_phone_presence():
    user_id = uuid4()
    repo = MagicMock()
    repo.list = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=user_id,
                names="Ana",
                lastnames="López",
                email="ana@example.com",
                phone=None,
            )
        ]
    )
    repo.rollback = AsyncMock()

    result = asyncio.run(ListUserNameUseCase(repo).execute(user_id=user_id))

    assert len(result) == 1
    payload = result[0].model_dump(mode="json")
    assert payload == {
        "id": str(user_id),
        "names": "Ana",
        "lastnames": "López",
        "has_email": True,
        "has_phone": False,
    }
    assert "email" not in payload
    assert "phone" not in payload


def test_updating_contact_data_broadcasts_client_status(monkeypatch):
    user_id = uuid4()
    update_use_case = MagicMock()
    update_use_case.execute = AsyncMock(return_value=SimpleNamespace(id=user_id))
    get_use_case = MagicMock()
    get_use_case.execute = AsyncMock(return_value=None)
    broadcast = AsyncMock()
    monkeypatch.setattr(user_routes, "broadcast_transaction_event", broadcast)

    result = asyncio.run(
        user_routes.update_user(
            form_data=(UserUpdateCmd(id=user_id, phone=51999999999), None),
            use_case=update_use_case,
            get_use_case=get_use_case,
            _permissions=[],
            audit_event=None,
        )
    )

    assert result.id == user_id
    broadcast.assert_awaited_once_with(
        "CLIENT_DATA_STATUS_UPDATED",
        {"user_id": str(user_id)},
    )
