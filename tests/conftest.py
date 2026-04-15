"""Fixtures para tests."""
import pytest
from unittest.mock import AsyncMock
from uuid import uuid4
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.modules.transactions.application.use_cases import CreateTransactionUseCase
from app.modules.transactions.application.schemas import TransactionReadDTO
from app.modules.transactions.domain.enums import TransactionStatus


@pytest.fixture
def mock_create_transaction_uc():
    """Mock de CreateTransactionUseCase que retorna una transacción creada."""
    use_case = AsyncMock(spec=CreateTransactionUseCase)
    created = TransactionReadDTO(
        id=uuid4(),
        bank_account_origin_id=uuid4(),
        bank_account_destination_id=uuid4(),
        user_id=uuid4(),
        tax_rate_id=uuid4(),
        commission_id=uuid4(),
        status=TransactionStatus.verification,
        origin_amount=100.0,
        destination_amount=95.0,
        code="TEST-001",
        commission_result=5.0,
        total_to_send=100.0,
        coupon_id=None,
        send_date=None,
        payment_date=None,
        send_voucher=None,
        payment_voucher=None,
        checked_image=None,
        checked=False,
        created_at=datetime.now(timezone.utc),
        created_by=None,
        updated_at=datetime.now(timezone.utc),
    )
    use_case.execute = AsyncMock(return_value=created)
    return use_case


@pytest.fixture
def override_create_uc(mock_create_transaction_uc):
    """Aplica override de CreateTransactionUseCase."""
    from app.modules.transactions.adapters.dependencies.transaction_dependencies import (
        create_transaction_uc,
    )

    app.dependency_overrides[create_transaction_uc] = lambda: mock_create_transaction_uc
    yield
    try:
        app.dependency_overrides.pop(create_transaction_uc)
    except KeyError:
        pass


@pytest.fixture
def client(override_create_uc):
    """Cliente HTTP para tests."""
    return TestClient(app)


@pytest.fixture
def valid_transaction_payload():
    """Payload JSON válido para crear transacción."""
    return {
        "bank_account_origin": str(uuid4()),
        "bank_account_destination": str(uuid4()),
        "user_id": str(uuid4()),
        "tax_rate_id": str(uuid4()),
        "commission_id": str(uuid4()),
        "status": "verification",
        "origin_amount": 100.0,
        "destination_amount": 95.0,
        "code": "TEST-001",
        "commission_result": 5.0,
        "total_to_send": 100.0,
    }
