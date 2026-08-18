# app/modules/transactions/adapters/router/transactions_websocket.py
"""Gestión de conexiones WebSocket y difusión de eventos en tiempo real para transacciones.

La difusión tiene dos capas:

1. **Local** (`TransactionConnectionManager`): reparte el mensaje a las conexiones
   de *este* proceso, filtrando por los permisos de cada suscriptor.
2. **Entre procesos** (`LISTEN`/`NOTIFY` de Postgres): replica el evento al resto
   de workers o réplicas. Reutiliza la base de datos que ya existe, así que no
   añade infraestructura. El emisor reparte en local de inmediato y sólo delega
   en `NOTIFY` la entrega a los demás procesos, de modo que una caída del canal
   degrada el tiempo real entre procesos pero nunca el del proceso que atendió
   la petición.
"""
import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import WebSocket
from sqlalchemy import select

from app.core.settings import get_settings
from app.modules.auth.infrastructure.jwt_service import decode_access_token

logger = logging.getLogger(__name__)

# Canal de Postgres para el fan-out entre procesos.
PG_EVENT_CHANNEL = "brasper_transactions_events"

# `NOTIFY` admite hasta 8000 bytes de payload. Dejamos margen para el sobre JSON:
# por encima de este tamaño se replica una versión reducida marcada con
# `partial`, y el cliente recarga la fila desde el REST.
_MAX_NOTIFY_PAYLOAD_BYTES = 6500

# Identifica a este proceso para que el listener ignore sus propios NOTIFY
# (ya se repartieron en local antes de publicar).
PROCESS_ID = str(uuid.uuid4())

# Tareas en vuelo (publicación y reparto asíncronos). Hay que mantener una
# referencia fuerte: `asyncio` sólo guarda una débil y el GC puede cancelar una
# task a medio camino.
_background_tasks: set = set()


def _spawn(coro) -> None:
    """Lanza una corrutina en segundo plano conservando su referencia."""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


@dataclass
class Subscriber:
    """Una conexión WebSocket junto al alcance de lectura que le corresponde."""

    websocket: WebSocket
    user_id: str
    can_view_all: bool


def _extract_owner_id(data: Any) -> Optional[str]:
    """Obtiene el `user_id` dueño de la transacción dentro del payload del evento."""
    if not isinstance(data, dict):
        return None
    direct = data.get("user_id")
    if direct:
        return str(direct)
    for key in ("user", "client"):
        nested = data.get(key)
        if isinstance(nested, dict) and nested.get("id"):
            return str(nested["id"])
    return None


class TransactionConnectionManager:
    def __init__(self):
        self._subscribers: Dict[WebSocket, Subscriber] = {}
        self._lock = asyncio.Lock()

    @property
    def connection_count(self) -> int:
        return len(self._subscribers)

    async def connect(self, websocket: WebSocket, user_id: str, can_view_all: bool) -> bool:
        await websocket.accept()
        async with self._lock:
            self._subscribers[websocket] = Subscriber(
                websocket=websocket,
                user_id=str(user_id),
                can_view_all=can_view_all,
            )
        logger.info(
            "WebSocket client connected (user=%s, scope=%s). Total connections: %s",
            user_id,
            "all" if can_view_all else "own",
            len(self._subscribers),
        )
        return True

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            self._subscribers.pop(websocket, None)
        logger.info("WebSocket client disconnected. Total connections: %s", len(self._subscribers))

    def _may_receive(self, subscriber: Subscriber, owner_id: Optional[str]) -> bool:
        """Replica el alcance del REST: sin `transactions.view` sólo lo propio.

        Si el evento no identifica a su dueño, un suscriptor restringido no lo
        recibe: preferimos perder una actualización antes que filtrar datos de
        otro cliente.
        """
        if subscriber.can_view_all:
            return True
        if not owner_id:
            return False
        return owner_id == subscriber.user_id

    async def dispatch_local(self, message: Dict[str, Any]):
        """Envía el mensaje a las conexiones de este proceso que tengan permiso."""
        async with self._lock:
            subscribers = list(self._subscribers.values())

        if not subscribers:
            return

        owner_id = _extract_owner_id(message.get("data"))
        payload = json.dumps(message, default=str)

        dead: List[WebSocket] = []
        for subscriber in subscribers:
            if not self._may_receive(subscriber, owner_id):
                continue
            try:
                await subscriber.websocket.send_text(payload)
            except Exception as e:
                logger.warning("Error sending message to WebSocket client: %s", e)
                dead.append(subscriber.websocket)

        if dead:
            async with self._lock:
                for connection in dead:
                    self._subscribers.pop(connection, None)


# Instancia singleton del gestor de conexiones
manager = TransactionConnectionManager()


def _serialize_event_data(data: Any) -> Dict[str, Any]:
    if hasattr(data, "model_dump"):
        return data.model_dump(mode="json")
    if hasattr(data, "dict"):
        return data.dict()
    if isinstance(data, dict):
        return data
    return {"data": str(data)}


def _build_notify_payload(message: Dict[str, Any]) -> str:
    """Serializa el mensaje para `NOTIFY`, recortándolo si excede el límite."""
    encoded = json.dumps(message, default=str)
    if len(encoded.encode("utf-8")) <= _MAX_NOTIFY_PAYLOAD_BYTES:
        return encoded

    data = message.get("data") if isinstance(message.get("data"), dict) else {}
    reduced = {
        "event": message.get("event"),
        "origin": message.get("origin"),
        "actor": message.get("actor") or {},
        "partial": True,
        "data": {
            "id": data.get("id"),
            "user_id": _extract_owner_id(data),
        },
    }
    return json.dumps(reduced, default=str)


async def _publish_to_other_processes(message: Dict[str, Any]) -> None:
    """Replica el evento al resto de procesos vía `NOTIFY`."""
    from app.db.base import engine
    from sqlalchemy import text

    payload = _build_notify_payload(message)
    try:
        async with engine.connect() as connection:
            await connection.execute(
                text("SELECT pg_notify(:channel, :payload)"),
                {"channel": PG_EVENT_CHANNEL, "payload": payload},
            )
            await connection.commit()
    except Exception as e:
        # El reparto local ya ocurrió: esto sólo afecta a los demás procesos.
        logger.warning("No se pudo replicar el evento %s vía NOTIFY: %s", message.get("event"), e)


async def broadcast_transaction_event(
    event_type: str,
    data: Any,
    actor: Optional[Dict[str, Any]] = None,
):
    """
    Difunde un evento de transacción a los clientes WebSocket conectados,
    en este proceso y en el resto de workers.
    `data` puede ser un diccionario, Pydantic model o DTO.
    """
    try:
        message = {
            "event": event_type,
            "data": _serialize_event_data(data),
            "actor": actor or {},
            "origin": PROCESS_ID,
        }
        # El reparto local es en memoria: instantáneo, y va inline para que el
        # proceso que atendió la petición no dependa de nada externo.
        await manager.dispatch_local(message)
        # La réplica al resto de procesos cuesta ~1s contra la BD remota (abrir
        # conexión + BEGIN/COMMIT). Se lanza en segundo plano: encadenarla al
        # request le sumaría ese tiempo a cada alta o edición de transacción.
        _spawn(_publish_to_other_processes(message))
    except Exception as e:
        logger.error("Failed to broadcast transaction event %s: %s", event_type, e)


async def authenticate_websocket(token: Optional[str]) -> Optional[Tuple[str, bool]]:
    """Valida el token del handshake y resuelve el alcance de lectura.

    Devuelve `(user_id, can_view_all)`, o `None` si la conexión debe rechazarse.
    `can_view_all` es cierto sólo si el rol del usuario tiene `transactions.view`,
    el mismo permiso que gobierna el listado REST.
    """
    settings = get_settings()
    if not settings.AUTH_REQUIRED:
        return ("anonymous", True)

    if not token or not token.strip():
        return None

    clean_token = token.strip()
    if clean_token.lower().startswith("bearer "):
        clean_token = clean_token[7:].strip()

    try:
        payload = decode_access_token(clean_token)
    except Exception as e:
        logger.warning("WebSocket authentication failed: %s", e)
        return None

    user_id = payload.get("sub")
    if not user_id:
        logger.warning("WebSocket authentication failed: token sin 'sub'")
        return None

    try:
        can_view_all = await _user_can_view_all_transactions(user_id)
    except Exception as e:
        logger.error("No se pudo resolver permisos del WebSocket para %s: %s", user_id, e)
        return None

    return (str(user_id), can_view_all)


async def _user_can_view_all_transactions(user_id: str) -> bool:
    """Carga el rol del usuario y comprueba `transactions.view`."""
    from app.db.base import AsyncSessionLocal
    from app.modules.auth.domain.models import RolePermissionModel
    from app.modules.users.domain.models import User

    async with AsyncSessionLocal() as session:
        user = await session.get(User, UUID(str(user_id)))
        if not user or user.deleted:
            raise ValueError(f"Usuario {user_id} no encontrado o eliminado")
        role = user.role or "user"
        permissions = (
            await session.execute(
                select(RolePermissionModel.permissions).where(
                    RolePermissionModel.role == role,
                    RolePermissionModel.deleted.is_(False),
                    RolePermissionModel.enable.is_(True),
                )
            )
        ).scalar_one_or_none() or []
        return "transactions.view" in permissions


class TransactionEventListener:
    """Escucha `NOTIFY` de Postgres y reparte los eventos a este proceso."""

    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._stopping = False

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stopping = False
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stopping = True
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except (asyncio.CancelledError, Exception):
            pass
        self._task = None

    async def _run(self) -> None:
        import asyncpg

        backoff = 1.0
        while not self._stopping:
            connection = None
            try:
                connection = await asyncpg.connect(get_settings().database_url)
                await connection.add_listener(PG_EVENT_CHANNEL, self._on_notify)
                logger.info("Escuchando eventos de transacciones en el canal '%s'", PG_EVENT_CHANNEL)
                backoff = 1.0
                while not self._stopping:
                    await asyncio.sleep(5)
                    # Detecta la conexión caída para reconectar con backoff.
                    await connection.execute("SELECT 1")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(
                    "Listener de eventos de transacciones caído (%s). Reintentando en %.0fs",
                    e,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
            finally:
                if connection is not None:
                    try:
                        await connection.close()
                    except Exception:
                        pass

    def _on_notify(self, _connection, _pid, _channel, payload: str) -> None:
        try:
            message = json.loads(payload)
        except Exception as e:
            logger.warning("Payload de NOTIFY inválido: %s", e)
            return
        if not isinstance(message, dict):
            return
        # El proceso emisor ya repartió el mensaje en local.
        if message.get("origin") == PROCESS_ID:
            return
        _spawn(manager.dispatch_local(message))


event_listener = TransactionEventListener()


async def handle_transactions_websocket(websocket: WebSocket, token: Optional[str]) -> None:
    """Handler único del canal de transacciones: handshake, heartbeat y cierre."""
    from fastapi import WebSocketDisconnect, status

    auth = await authenticate_websocket(token)
    if not auth:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id, can_view_all = auth
    await manager.connect(websocket, user_id=user_id, can_view_all=can_view_all)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                parsed = json.loads(data)
            except Exception:
                continue
            if isinstance(parsed, dict) and (parsed.get("type") == "ping" or parsed.get("event") == "ping"):
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:
        await manager.disconnect(websocket)
