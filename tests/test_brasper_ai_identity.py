"""Identity supplied in a conversation cannot overwrite an existing client."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.brasper.application.ai_schemas import AIClientUpsertCmd
from app.modules.brasper.application.ai_service import BrasperAIService


def command():
    return AIClientUpsertCmd(names="Otro", lastnames="Nombre", document_type="dni",
                             document_number="12345678", code_phone="+51", phone=999111222)


@pytest.mark.parametrize("match_document,match_phone", [(True, False), (False, True)])
async def test_single_match_cannot_reassign_client(match_document, match_phone):
    session = MagicMock()
    session.commit = AsyncMock()
    user = SimpleNamespace(id=uuid4(), names="Original", phone=999444555)
    service = BrasperAIService(session)
    service._find_by_document = AsyncMock(return_value=user if match_document else None)
    service._find_by_phone = AsyncMock(return_value=user if match_phone else None)
    with pytest.raises(ValueError, match="verificación"):
        await service.upsert_client(command())
    assert user.names == "Original" and user.phone == 999444555
    session.add.assert_not_called()
    session.commit.assert_not_awaited()


async def test_matching_client_is_returned_without_rewriting_profile():
    session = MagicMock()
    session.commit = AsyncMock()
    user = SimpleNamespace(id=uuid4(), names="Original", phone=999111222)
    service = BrasperAIService(session)
    service._find_by_document = AsyncMock(return_value=user)
    service._find_by_phone = AsyncMock(return_value=user)
    service._is_first_transfer = AsyncMock(return_value=False)
    result = await service.upsert_client(command())
    assert result.id == user.id and not result.created and not result.is_first_transfer
    assert user.names == "Original"
    session.add.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.parametrize("completed,pending,eligible", [(0, 0, True), (0, 1, False), (1, 0, False), (2, 3, False)])
async def test_history_eligibility_includes_pending_reservation(completed, pending, eligible):
    session = MagicMock()
    session.scalars = AsyncMock(return_value=SimpleNamespace(first=lambda: object()))
    session.scalar = AsyncMock(side_effect=[completed, pending])
    result = await BrasperAIService(session).client_history(uuid4(), code_phone="+51", phone=999111222)
    assert result.completed_transfers == completed and result.pending_transfers == pending
    assert result.first_transfer_eligible is eligible


async def test_history_does_not_query_operations_for_unmatched_identity():
    session = MagicMock()
    session.scalars = AsyncMock(return_value=SimpleNamespace(first=lambda: None))
    session.scalar = AsyncMock()
    result = await BrasperAIService(session).client_history(uuid4(), code_phone="+51", phone=999111222)
    assert result is None
    session.scalar.assert_not_awaited()


async def test_operation_status_rejects_unmatched_identity_before_reading_operations():
    session = MagicMock()
    session.scalars = AsyncMock(return_value=SimpleNamespace(first=lambda: None))
    assert await BrasperAIService(session).operation_status(uuid4(), code_phone="+51", phone=999111222) is None
    assert session.scalars.await_count == 1


async def test_operation_status_query_filters_owner_reference_and_private_data():
    from datetime import datetime, timezone
    user_id, other_operation = uuid4(), uuid4()
    session = MagicMock()
    session.scalars = AsyncMock(side_effect=[SimpleNamespace(first=lambda: object()),
        SimpleNamespace(all=lambda: [SimpleNamespace(code="PxB-123", status="verification", updated_at=datetime.now(timezone.utc))])])
    result = await BrasperAIService(session).operation_status(user_id, code_phone="+51", phone=999111222, reference=str(other_operation))
    stmt = session.scalars.call_args.args[0]
    compiled = stmt.compile()
    assert user_id in compiled.params.values() and other_operation in compiled.params.values()
    assert "user_id" in str(stmt) and "deleted IS false" in str(stmt) and "LIMIT" in str(stmt)
    assert set(result[0].model_dump()) == {"code", "status", "updated_at"}
