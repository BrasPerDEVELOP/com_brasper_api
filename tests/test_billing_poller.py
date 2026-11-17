"""Poller de comprobantes: el bloqueo consultivo se toma y se libera en la MISMA conexión."""
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

import app.db.base as db_base
from app.core.settings import get_settings
from app.modules.billing.infrastructure import poller as poller_module
from app.modules.billing.infrastructure.poller import InvoicePoller


class FakeConn:
    def __init__(self, name, locked=True):
        self.name = name
        self.locked = locked
        self.statements: list[str] = []

    async def execute(self, statement, params=None):
        sql = str(statement)
        self.statements.append(sql)
        return SimpleNamespace(scalar=lambda: self.locked if "try_advisory_lock" in sql else True)

    async def commit(self):
        pass


@pytest.fixture
def billing_on(monkeypatch):
    settings = get_settings().model_copy(update={"BILLING_ENABLED": True, "OMIE_ENABLED": False})
    monkeypatch.setattr(poller_module, "get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.modules.billing.adapters.dependencies.build_apisunat_client", lambda s: object()
    )
    return settings


def _wire(monkeypatch, lock_conn, calls):
    @asynccontextmanager
    async def connect():
        yield lock_conn

    @asynccontextmanager
    async def session_factory():
        yield SimpleNamespace(name="sesion-orm")

    monkeypatch.setattr(db_base, "engine", SimpleNamespace(connect=connect))
    monkeypatch.setattr(db_base, "AsyncSessionLocal", session_factory)

    class FakeRecover:
        def __init__(self, *a, **k):
            pass

        async def execute(self):
            calls.append("recover")
            return 1

    class FakePending:
        def __init__(self, *a, **k):
            pass

        async def execute(self):
            calls.append("poll")
            return 2

    class FakeEmailDelivery:
        def __init__(self, *a, **k):
            pass

        async def execute(self):
            calls.append("email")
            return 0

    import app.modules.billing.application.use_cases as uc

    monkeypatch.setattr(uc, "RecoverStaleReservedUseCase", FakeRecover)
    monkeypatch.setattr(uc, "PollPendingInvoicesUseCase", FakePending)
    monkeypatch.setattr(uc, "DeliverPendingInvoiceEmailsUseCase", FakeEmailDelivery)


@pytest.mark.asyncio
async def test_lock_y_unlock_en_la_misma_conexion(monkeypatch, billing_on):
    lock_conn, calls = FakeConn("lock"), []
    _wire(monkeypatch, lock_conn, calls)

    assert await InvoicePoller().tick() == 3
    assert calls == ["recover", "poll", "email"]
    assert any("pg_try_advisory_lock" in s for s in lock_conn.statements)
    assert any("pg_advisory_unlock" in s for s in lock_conn.statements)


@pytest.mark.asyncio
async def test_sin_lock_no_trabaja(monkeypatch, billing_on):
    lock_conn, calls = FakeConn("lock", locked=False), []
    _wire(monkeypatch, lock_conn, calls)

    assert await InvoicePoller().tick() == 0
    assert calls == []
    assert not any("pg_advisory_unlock" in s for s in lock_conn.statements)


@pytest.mark.asyncio
async def test_omie_email_runs_when_sunat_is_disabled(monkeypatch, billing_on):
    from unittest.mock import AsyncMock
    from app.modules.omie.application.email_delivery import OmieEmailService

    billing_on.BILLING_ENABLED = False
    billing_on.OMIE_ENABLED = True
    lock_conn, calls = FakeConn("lock"), []
    _wire(monkeypatch, lock_conn, calls)
    monkeypatch.setattr(OmieEmailService, "__init__", lambda *a, **k: None)
    deliver = AsyncMock(return_value=1)
    monkeypatch.setattr(OmieEmailService, "deliver_pending", deliver)

    assert await InvoicePoller().tick() == 0
    deliver.assert_awaited_once()
    assert calls == []
    assert any("pg_advisory_unlock" in s for s in lock_conn.statements)
