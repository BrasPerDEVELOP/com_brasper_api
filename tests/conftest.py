"""Fixtures para tests."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.db.base import get_db
from app.modules.transactions.application.use_cases import CreateTransactionUseCase, UpdateTransactionUseCase
from app.modules.transactions.application.schemas import TransactionReadDTO, TransactionUserRef
from app.modules.transactions.domain.enums import TransactionStatus


@pytest.fixture(autouse=True)
def pinned_auth_requirement():
    """
    Fija `AUTH_REQUIRED=False` como base de cada test.

    `get_settings()` está cacheado y lee el `.env` del desarrollador, así que sin
    esto el resultado de la suite depende de una variable local: con
    `AUTH_REQUIRED=true` el middleware corta con 401 todos los tests que no
    construyen un token, y con `false` pasan. Los tests que sí verifican
    autorización ponen `AUTH_REQUIRED = True` explícitamente y lo restauran.
    """
    from app.core.settings import get_settings

    settings = get_settings()
    previous = settings.AUTH_REQUIRED
    settings.AUTH_REQUIRED = False
    try:
        yield
    finally:
        settings.AUTH_REQUIRED = previous


@pytest.fixture(autouse=True)
def isolate_failed_audit_session(monkeypatch):
    """Impide que los tests HTTP abran la base real al auditar respuestas fallidas."""
    audit_db = MagicMock()
    audit_db.commit = AsyncMock()

    class FakeSessionContext:
        async def __aenter__(self):
            return audit_db

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr(
        "app.modules.audit.infrastructure.failed_mutation_middleware.AsyncSessionLocal",
        lambda: FakeSessionContext(),
    )
    return audit_db


@pytest.fixture
def mock_create_transaction_uc():
    """Mock de CreateTransactionUseCase que retorna una transacción creada."""
    use_case = AsyncMock(spec=CreateTransactionUseCase)
    uid = uuid4()
    created = TransactionReadDTO(
        id=uuid4(),
        bank_account_origin_id=uuid4(),
        bank_account_destination_id=uuid4(),
        user_id=uid,
        tax_rate_id=uuid4(),
        commission_id=uuid4(),
        status=TransactionStatus.verification,
        origin_amount=100.0,
        destination_amount=95.0,
        code="TEST-001",
        operation_number=None,
        commission_result=5.0,
        total_to_send=100.0,
        tax_amount=None,
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
        user=TransactionUserRef(id=uid, role=None),
    )
    use_case.execute = AsyncMock(return_value=created)
    return use_case


@pytest.fixture
def mock_update_transaction_uc():
    """Mock de UpdateTransactionUseCase que retorna una transacción actualizada."""
    use_case = AsyncMock(spec=UpdateTransactionUseCase)
    uid = uuid4()
    updated = TransactionReadDTO(
        id=uuid4(),
        bank_account_origin_id=uuid4(),
        bank_account_destination_id=uuid4(),
        user_id=uid,
        tax_rate_id=uuid4(),
        commission_id=uuid4(),
        status=TransactionStatus.verification,
        origin_amount=100.0,
        destination_amount=95.0,
        code="TEST-001",
        operation_number=None,
        commission_result=5.0,
        total_to_send=100.0,
        tax_amount=None,
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
        user=TransactionUserRef(id=uid, role=None),
    )
    use_case.execute = AsyncMock(return_value=updated)
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
def override_update_uc(mock_update_transaction_uc):
    """Aplica override de UpdateTransactionUseCase."""
    from app.modules.transactions.adapters.dependencies.transaction_dependencies import (
        update_transaction_uc,
    )

    app.dependency_overrides[update_transaction_uc] = lambda: mock_update_transaction_uc
    yield
    try:
        app.dependency_overrides.pop(update_transaction_uc)
    except KeyError:
        pass


@pytest.fixture
def client(override_create_uc, override_update_uc, mock_update_transaction_uc):
    """Cliente HTTP para tests."""
    db = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    app.dependency_overrides[get_db] = lambda: db
    from app.modules.transactions.adapters.dependencies.transaction_dependencies import (
        get_transaction_by_id_uc,
    )
    get_use_case = MagicMock()
    get_use_case.execute = AsyncMock(return_value=mock_update_transaction_uc.execute.return_value)
    app.dependency_overrides[get_transaction_by_id_uc] = lambda: get_use_case
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_transaction_by_id_uc, None)


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
