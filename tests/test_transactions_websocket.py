# tests/test_transactions_websocket.py
"""Tests del canal WebSocket de transacciones: handshake, alcance y fan-out."""
import asyncio
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import app
from app.modules.auth.infrastructure.jwt_service import create_access_token
from app.modules.transactions.adapters.router import transactions_websocket as ws_module
from app.modules.transactions.adapters.router.transactions_websocket import (
    PROCESS_ID,
    Subscriber,
    TransactionConnectionManager,
    _build_notify_payload,
    _extract_owner_id,
    authenticate_websocket,
    broadcast_transaction_event,
    manager,
)


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def no_cross_process_publish(monkeypatch):
    """Evita que los tests abran la base real para hacer `NOTIFY`."""
    published: list[dict] = []

    async def fake_publish(message):
        published.append(message)

    monkeypatch.setattr(ws_module, "_publish_to_other_processes", fake_publish)
    return published


class FakeWebSocket:
    """Doble de WebSocket que sólo acumula lo que se le envía."""

    def __init__(self):
        self.sent: list[dict] = []

    async def accept(self):
        return None

    async def send_text(self, payload: str):
        self.sent.append(json.loads(payload))


def test_websocket_ping_pong(test_client):
    """La conexión responde al heartbeat ping con un pong."""
    token, _ = create_access_token(user_id=uuid.uuid4(), session_id=uuid.uuid4())

    with test_client.websocket_connect(f"/ws/transactions/?token={token}") as websocket:
        websocket.send_json({"type": "ping"})
        assert websocket.receive_json().get("type") == "pong"


def test_websocket_receives_broadcast_event(test_client):
    """Los eventos difundidos llegan a los clientes conectados."""
    token, _ = create_access_token(user_id=uuid.uuid4(), session_id=uuid.uuid4())

    with test_client.websocket_connect(f"/ws/transactions/?token={token}") as websocket:
        tx = {"id": str(uuid.uuid4()), "status": "completed", "origin_amount": 250.0}
        asyncio.run(broadcast_transaction_event("TRANSACTION_CREATED", tx))

        received = websocket.receive_json()
        assert received.get("event") == "TRANSACTION_CREATED"
        assert received.get("data", {}).get("id") == tx["id"]
        assert received.get("data", {}).get("status") == "completed"


# --- Alcance por permisos -----------------------------------------------------


def test_extract_owner_id_from_alternative_shapes():
    """El dueño se resuelve de `user_id`, `user.id` o `client.id`."""
    assert _extract_owner_id({"user_id": "u1"}) == "u1"
    assert _extract_owner_id({"user": {"id": "u2"}}) == "u2"
    assert _extract_owner_id({"client": {"id": "u3"}}) == "u3"
    assert _extract_owner_id({"id": "tx"}) is None
    assert _extract_owner_id(None) is None


def test_scoped_subscriber_only_receives_own_transactions():
    """Sin `transactions.view` un suscriptor sólo recibe lo suyo."""
    local_manager = TransactionConnectionManager()
    owner_ws, other_ws, admin_ws = FakeWebSocket(), FakeWebSocket(), FakeWebSocket()

    asyncio.run(local_manager.connect(owner_ws, user_id="user-1", can_view_all=False))
    asyncio.run(local_manager.connect(other_ws, user_id="user-2", can_view_all=False))
    asyncio.run(local_manager.connect(admin_ws, user_id="admin-1", can_view_all=True))

    asyncio.run(
        local_manager.dispatch_local(
            {"event": "TRANSACTION_UPDATED", "data": {"id": "tx-1", "user_id": "user-1"}}
        )
    )

    assert len(owner_ws.sent) == 1
    assert owner_ws.sent[0]["data"]["id"] == "tx-1"
    assert other_ws.sent == []
    assert len(admin_ws.sent) == 1


def test_scoped_subscriber_does_not_receive_ownerless_events():
    """Un evento sin dueño identificable no llega a los suscriptores restringidos."""
    local_manager = TransactionConnectionManager()
    scoped_ws, admin_ws = FakeWebSocket(), FakeWebSocket()

    asyncio.run(local_manager.connect(scoped_ws, user_id="user-1", can_view_all=False))
    asyncio.run(local_manager.connect(admin_ws, user_id="admin-1", can_view_all=True))

    asyncio.run(
        local_manager.dispatch_local({"event": "TRANSACTIONS_BULK_IMPORTED", "data": {"count": 12}})
    )

    assert scoped_ws.sent == []
    assert len(admin_ws.sent) == 1


def test_disconnect_removes_subscriber():
    local_manager = TransactionConnectionManager()
    ws = FakeWebSocket()
    asyncio.run(local_manager.connect(ws, user_id="user-1", can_view_all=True))
    assert local_manager.connection_count == 1

    asyncio.run(local_manager.disconnect(ws))
    assert local_manager.connection_count == 0

    asyncio.run(local_manager.dispatch_local({"event": "TRANSACTION_CREATED", "data": {"id": "x"}}))
    assert ws.sent == []


# --- Handshake ----------------------------------------------------------------


def test_authenticate_websocket_rejects_missing_and_invalid_token():
    """Con autenticación activa, un token ausente o alterado no conecta."""
    settings = get_settings()
    settings.AUTH_REQUIRED = True
    try:
        assert asyncio.run(authenticate_websocket(None)) is None
        assert asyncio.run(authenticate_websocket("   ")) is None
        assert asyncio.run(authenticate_websocket("no-es-un-jwt")) is None
    finally:
        settings.AUTH_REQUIRED = False


def test_authenticate_websocket_resolves_scope_from_role_permissions(monkeypatch):
    """El alcance sale del permiso `transactions.view` del rol."""
    settings = get_settings()
    settings.AUTH_REQUIRED = True
    user_id = uuid.uuid4()
    token, _ = create_access_token(user_id=user_id, session_id=uuid.uuid4())
    try:
        async def can_view_all(_user_id):
            return True

        monkeypatch.setattr(ws_module, "_user_can_view_all_transactions", can_view_all)
        assert asyncio.run(authenticate_websocket(token)) == (str(user_id), True)

        async def cannot_view_all(_user_id):
            return False

        monkeypatch.setattr(ws_module, "_user_can_view_all_transactions", cannot_view_all)
        assert asyncio.run(authenticate_websocket(token)) == (str(user_id), False)
    finally:
        settings.AUTH_REQUIRED = False


def test_authenticate_websocket_rejects_when_user_lookup_fails(monkeypatch):
    """Si no se puede resolver el usuario, la conexión se rechaza (fail-closed)."""
    settings = get_settings()
    settings.AUTH_REQUIRED = True
    token, _ = create_access_token(user_id=uuid.uuid4(), session_id=uuid.uuid4())
    try:
        async def boom(_user_id):
            raise ValueError("usuario no encontrado")

        monkeypatch.setattr(ws_module, "_user_can_view_all_transactions", boom)
        assert asyncio.run(authenticate_websocket(token)) is None
    finally:
        settings.AUTH_REQUIRED = False


def test_websocket_closes_when_token_is_invalid(test_client):
    """El endpoint cierra la conexión si el handshake no autentica."""
    from starlette.websockets import WebSocketDisconnect

    settings = get_settings()
    settings.AUTH_REQUIRED = True
    try:
        with pytest.raises(WebSocketDisconnect):
            with test_client.websocket_connect("/ws/transactions/?token=invalido") as websocket:
                websocket.receive_json()
    finally:
        settings.AUTH_REQUIRED = False


# --- Fan-out entre procesos ---------------------------------------------------


def test_broadcast_publishes_to_other_processes(no_cross_process_publish):
    """Cada evento se reparte en local y se replica al resto de procesos."""

    async def scenario():
        await broadcast_transaction_event("TRANSACTION_CREATED", {"id": "tx-1", "user_id": "u1"})
        await asyncio.sleep(0)  # deja correr la publicación en segundo plano

    asyncio.run(scenario())

    assert len(no_cross_process_publish) == 1
    message = no_cross_process_publish[0]
    assert message["event"] == "TRANSACTION_CREATED"
    assert message["origin"] == PROCESS_ID


def test_broadcast_does_not_block_on_cross_process_publish(monkeypatch):
    """La réplica lenta no debe retrasar la respuesta del endpoint.

    El `NOTIFY` cuesta ~1s contra la base remota; si se encadenara al request,
    cada alta o edición de transacción pagaría esa espera.
    """
    started = asyncio.Event()

    async def slow_publish(_message):
        started.set()
        await asyncio.sleep(5)

    monkeypatch.setattr(ws_module, "_publish_to_other_processes", slow_publish)

    async def scenario():
        ws = FakeWebSocket()
        await manager.connect(ws, user_id="u1", can_view_all=True)
        try:
            loop = asyncio.get_running_loop()
            start = loop.time()
            await broadcast_transaction_event("TRANSACTION_CREATED", {"id": "tx-1", "user_id": "u1"})
            elapsed = loop.time() - start
            await asyncio.sleep(0)
            return elapsed, started.is_set(), ws.sent
        finally:
            await manager.disconnect(ws)

    elapsed, publish_started, sent = asyncio.run(scenario())

    assert elapsed < 1.0, f"el broadcast bloqueó {elapsed:.2f}s esperando la réplica"
    assert publish_started, "la réplica debe lanzarse, no descartarse"
    # El suscriptor local recibió el evento sin esperar la réplica.
    assert len(sent) == 1 and sent[0]["data"]["id"] == "tx-1"


def test_notify_payload_is_reduced_when_it_exceeds_the_limit():
    """Un payload que no cabe en `NOTIFY` se replica marcado como `partial`."""
    big = {
        "event": "TRANSACTION_UPDATED",
        "origin": PROCESS_ID,
        "actor": {},
        "data": {"id": "tx-1", "user_id": "u1", "notes": "x" * 9000},
    }
    reduced = json.loads(_build_notify_payload(big))

    assert reduced["partial"] is True
    assert reduced["data"] == {"id": "tx-1", "user_id": "u1"}
    assert len(json.dumps(reduced).encode("utf-8")) < 8000


def test_notify_payload_is_untouched_when_it_fits():
    small = {"event": "TRANSACTION_CREATED", "origin": PROCESS_ID, "actor": {}, "data": {"id": "tx-1"}}
    assert json.loads(_build_notify_payload(small)) == small


def test_listener_ignores_its_own_notify_echo():
    """El emisor ya repartió en local: su propio NOTIFY no se vuelve a repartir."""
    ws = FakeWebSocket()
    asyncio.run(manager.connect(ws, user_id="u1", can_view_all=True))
    try:
        listener = ws_module.TransactionEventListener()
        own = json.dumps({"event": "TRANSACTION_CREATED", "origin": PROCESS_ID, "data": {"id": "tx-1"}})
        listener._on_notify(None, 0, ws_module.PG_EVENT_CHANNEL, own)
        assert ws.sent == []
    finally:
        asyncio.run(manager.disconnect(ws))


def test_listener_dispatches_notify_from_another_process():
    """Un NOTIFY de otro proceso sí se reparte a las conexiones locales."""

    async def scenario():
        ws = FakeWebSocket()
        local = TransactionConnectionManager()
        await local.connect(ws, user_id="u1", can_view_all=True)

        listener = ws_module.TransactionEventListener()
        foreign = json.dumps(
            {"event": "TRANSACTION_CREATED", "origin": "otro-proceso", "data": {"id": "tx-9"}}
        )
        original = ws_module.manager
        ws_module.manager = local
        try:
            listener._on_notify(None, 0, ws_module.PG_EVENT_CHANNEL, foreign)
            await asyncio.sleep(0)  # deja correr la task creada por el listener
        finally:
            ws_module.manager = original
        return ws.sent

    sent = asyncio.run(scenario())
    assert len(sent) == 1
    assert sent[0]["data"]["id"] == "tx-9"


def test_listener_ignores_malformed_notify_payload():
    listener = ws_module.TransactionEventListener()
    listener._on_notify(None, 0, ws_module.PG_EVENT_CHANNEL, "{no-es-json")
    listener._on_notify(None, 0, ws_module.PG_EVENT_CHANNEL, '"solo-un-string"')
