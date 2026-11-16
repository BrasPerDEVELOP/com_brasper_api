from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.modules.transactions.application.schemas import TransactionUpdateCmd
from app.modules.transactions.application.use_cases.transaction_use_cases import UpdateTransactionUseCase


@pytest.mark.asyncio
async def test_accounting_date_update_does_not_recalculate_operation():
    date = datetime(2026, 11, 16, tzinfo=timezone.utc)
    entity = SimpleNamespace(id=uuid4(), billing_date=None)
    repo = SimpleNamespace(get=AsyncMock(return_value=entity), update=AsyncMock(),
                           commit=AsyncMock(), refresh=AsyncMock())
    bank = SimpleNamespace(get=AsyncMock())
    service = UpdateTransactionUseCase(repo, bank, bank, bank)
    with patch("app.modules.transactions.application.use_cases.transaction_use_cases.TransactionReadDTO.model_validate", return_value=entity):
        result = await service.execute(TransactionUpdateCmd(id=entity.id, billing_date=date))
    assert result.billing_date == date
    repo.update.assert_awaited_once_with(entity)
    repo.commit.assert_awaited_once()
    bank.get.assert_not_awaited()
