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
    settings = get_settings().model_copy(update={"BILLING_ENABLED": True})
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

    import app.modules.billing.application.use_cases as uc

    monkeypatch.setattr(uc, "RecoverStaleReservedUseCase", FakeRecover)
    monkeypatch.setattr(uc, "PollPendingInvoicesUseCase", FakePending)


@pytest.mark.asyncio
async def test_lock_y_unlock_en_la_misma_conexion(monkeypatch, billing_on):
    lock_conn, calls = FakeConn("lock"), []
    _wire(monkeypatch, lock_conn, calls)

    assert await InvoicePoller().tick() == 3
    assert calls == ["recover", "poll"]
    assert any("pg_try_advisory_lock" in s for s in lock_conn.statements)
    assert any("pg_advisory_unlock" in s for s in lock_conn.statements)


@pytest.mark.asyncio
async def test_sin_lock_no_trabaja(monkeypatch, billing_on):
    lock_conn, calls = FakeConn("lock", locked=False), []
    _wire(monkeypatch, lock_conn, calls)

    assert await InvoicePoller().tick() == 0
    assert calls == []
    assert not any("pg_advisory_unlock" in s for s in lock_conn.statements)
