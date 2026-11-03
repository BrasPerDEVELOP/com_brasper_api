from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.users.application.schemas.user_schema import UserReadDTO, UserReadGeneralDTO
from app.modules.users.application.use_cases.user_use_cases import ListUserUseCase
from unittest.mock import AsyncMock


def record(phone):
    return SimpleNamespace(
        id=uuid4(), phone=phone,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )


@pytest.mark.parametrize("dto", [UserReadDTO, UserReadGeneralDTO])
@pytest.mark.parametrize("phone,expected", [
    ("992 836 506", 992836506), ("992\u00a0836\u00a0506", 992836506),
    (992836506, 992836506), ("992836506", 992836506),
    (None, None), ("   ", None),
])
def test_read_phone_accepts_legacy_spaces_without_mutating_record(dto, phone, expected):
    user = record(phone)
    assert dto.model_validate(user).phone == expected
    assert user.phone == phone


@pytest.mark.parametrize("dto", [UserReadDTO, UserReadGeneralDTO])
@pytest.mark.parametrize("phone", ["@legacy_contact", "+51 992-836-506", "992abc836506"])
def test_read_phone_preserves_legacy_text(dto, phone):
    assert dto.model_validate(record(phone)).phone == phone


@pytest.mark.asyncio
async def test_list_users_survives_formatted_phone():
    repo = AsyncMock()
    repo.list_filtered.return_value = [record(123456789), record("992 836 506")]
    users = await ListUserUseCase(repo).execute()
    assert [user.phone for user in users] == [123456789, 992836506]
    repo.rollback.assert_not_awaited()
