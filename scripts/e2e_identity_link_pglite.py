"""Arnés E2E (laboratorio) de la vinculación de identidad del chat contra PGlite.

Levanta la app REAL ``app.main:app`` con uvicorn en 127.0.0.1 (hilo propio) sobre
una base PGlite (PostgreSQL 18 WASM por protocolo PG) ya migrada a ``head`` con
``scripts/validate_migrations_pglite.py``. Lo usa el bot (com_brasper_ia,
``backend/tests/identity_e2e.py``) por HTTP como lo haría en producción.

Nada de producción:
  * El proceso cambia de directorio a una carpeta temporal ANTES de importar la app,
    así ``Settings`` (env_file=".env" relativo al cwd) no encuentra ningún ``.env``;
    toda la configuración sale de variables sintéticas fijadas aquí.
  * ``POSTGRES_*`` apuntan al PGlite local; además ``app.db.base.engine`` y
    ``AsyncSessionLocal`` se reemplazan por un engine a PGlite con UNA conexión
    (``pool_size=1, max_overflow=0``): PGlite ejecuta una sola sesión de backend.
  * Solo escucha en 127.0.0.1.

Qué se reemplaza / desactiva (y por qué):
  * ``lifespan`` de la app: el original verifica Cloudflare R2 y arranca el listener
    LISTEN/NOTIFY de transacciones (red externa / segunda conexión). Se sustituye
    por uno que solo siembra datos sintéticos.
  * Sesión del portal: ``TokenAuthMiddleware._authenticate_token`` acepta además
    ``Bearer e2e-portal.<uuid>`` y devuelve ese usuario como cliente autenticado.
    Es la simulación de "el cliente X inició sesión en el portal" (equivale a
    sobrescribir ``get_current_user``, que lee lo que el middleware fija, pero
    funciona también con ``AUTH_REQUIRED=True``). Cualquier otro token sigue la
    ruta real (JWT/opaco contra BD).
  * Rutas ``/__e2e/*`` de control (solo en este arnés, despachadas ANTES de la app
    real y protegidas con ``X-E2E-Control``): manipular vencimientos en BD, listar
    vínculos sin hashes y apagar el servidor. El bot no puede abrir una segunda
    conexión a PGlite, por eso la manipulación de BD pasa por aquí.
  * Cuenta de servicio del bot (NO simulada): se siembra ``user.auth_login`` con el
    hash real de ``SecurityUtils.hash_password`` (Argon2) y un ``user.user`` con rol
    ``user`` (sin teléfono, no es cliente). El bot entra por el ``POST /auth/login``
    real y usa el JWT real (``_verify_jwt`` contra ``user.auth_session``).

Uso (desde la raíz de com_brasper_api, PGlite ya migrado)::

    set E2E_SHARED_SECRET=<valor sintético>
    .venv/Scripts/python.exe scripts/e2e_identity_link_pglite.py --pg-port 55450 --port 8010

Variables: ``E2E_SHARED_SECRET`` (obligatoria, sintética), ``E2E_AUTH_REQUIRED``
(``1`` por defecto: como fuera de desarrollo), ``E2E_SERVICE_USERNAME`` y
``E2E_SERVICE_PASSWORD`` (cuenta de servicio sintética; sin ellas no se siembra).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import tempfile
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]

# IDs y códigos sintéticos fijos (el bot de prueba los recibe por /__e2e/seed).
OWNER_ID = UUID("0e2e0000-0000-4000-8000-000000000001")
OTHER_ID = UUID("0e2e0000-0000-4000-8000-000000000002")
OWNER_OPS = [("E2E-OWN-001", "verification"), ("E2E-OWN-002", "completed")]
OWNER_DELETED_OP = ("E2E-OWN-DEL", "failed")  # deleted=true: nunca debe salir
OTHER_OPS = [("E2E-OTH-001", "failed"), ("E2E-OTH-002", "verified")]
SERVICE_ID = UUID("0e2e0000-0000-4000-8000-0000000000a1")


def _configure_env(pg_port: int, secret: str, auth_required: bool) -> None:
    synthetic = {
        "POSTGRES_DB": "postgres", "POSTGRES_USER": "postgres", "POSTGRES_PASSWORD": "postgres",
        "POSTGRES_HOST": "127.0.0.1", "POSTGRES_PORT": str(pg_port),
        "DEBUG": "false", "LOG_LEVEL": "WARNING", "ENVIRONMENT": "development",
        "AUTH_REQUIRED": "true" if auth_required else "false", "AUTH_MODE": "dual",
        "ROOT_PATH": "", "PUBLIC_URL": "", "FRONTEND_URL": "",
        "SECRET_KEY": "e2e-synthetic-secret-key-not-for-prod-000000",
        "JWT_SECRET_KEY": "e2e-synthetic-jwt-key-not-for-prod-0000000000",
        "BRASPER_IA_SHARED_SECRET": secret,
        "BRASPER_IA_IDENTITY_LINK_ENABLED": "true",
        "R2_ENDPOINT_URL": "http://127.0.0.1:9", "R2_ACCESS_KEY_ID": "e2e", "R2_SECRET_ACCESS_KEY": "e2e",
        "R2_BUCKET_NAME": "e2e", "R2_PUBLIC_URL": "", "MEDIA_SIGNING_SECRET": "",
        "SMTP_HOST": "", "SMTP_USERNAME": "", "SMTP_PASSWORD": "", "SMTP_FROM_EMAIL": "",
        "FOOTBALL_DATA_API_TOKEN": "", "SPORTMONKS_API_TOKEN": "", "WORLD_CUP_SCHEDULER_ENABLED": "false",
    }
    os.environ.update(synthetic)


def build_app(pg_port: int, secret: str, auth_required: bool):
    # Sin .env: Settings lee env_file relativo al cwd.
    os.chdir(tempfile.mkdtemp(prefix="e2e_identity_api_"))
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    _configure_env(pg_port, secret, auth_required)

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    import app.db.base as base

    engine = create_async_engine(
        f"postgresql+asyncpg://postgres:postgres@127.0.0.1:{pg_port}/postgres"
        "?prepared_statement_cache_size=0",
        pool_size=1, max_overflow=0, pool_timeout=20, pool_pre_ping=False,
        connect_args={"ssl": False, "statement_cache_size": 0},
    )
    session_local = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False,
                                 autoflush=False, autocommit=False)
    base.engine = engine
    base.AsyncSessionLocal = session_local

    from app.core.settings import get_settings
    settings = get_settings()
    assert settings.database_url.endswith(f"@127.0.0.1:{pg_port}/postgres"), "BD no es PGlite local"
    assert settings.BRASPER_IA_IDENTITY_LINK_ENABLED and settings.BRASPER_IA_SHARED_SECRET == secret

    from app.main import app
    from app.middlewares.auth import TokenAuthMiddleware

    original_auth = TokenAuthMiddleware._authenticate_token

    async def portal_session(self, token: str):
        # Simulación de la sesión del portal: "el cliente <uuid> inició sesión".
        if token.startswith("e2e-portal."):
            try:
                user_id = UUID(token.split(".", 1)[1])
            except ValueError:
                return None
            return {"user_id": str(user_id), "session_id": "e2e-portal", "username": f"e2e-{user_id}",
                    "role": "client", "client_app": "www"}
        return await original_auth(self, token)

    TokenAuthMiddleware._authenticate_token = portal_session

    @asynccontextmanager
    async def e2e_lifespan(_app):
        # Reemplaza el lifespan real (R2 + listener LISTEN/NOTIFY): solo siembra.
        await seed(engine)
        await seed_service_account(engine)
        yield

    app.router.lifespan_context = e2e_lifespan

    control = build_control_app(engine, secret)

    async def outer(scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith("/__e2e/"):
            await control(scope, receive, send)
        else:
            await app(scope, receive, send)

    return outer, control


async def seed(engine) -> None:
    from sqlalchemy import text
    async with engine.begin() as conn:
        exists = (await conn.execute(text('SELECT 1 FROM "user"."user" WHERE id=:i'), {"i": OWNER_ID})).first()
        if exists:
            return
        for uid, names, code_phone, phone, email in (
                (OWNER_ID, "Cliente Dueño E2E", "+51", 900000001, "owner.e2e@example.com"),
                (OTHER_ID, "Cliente Otro E2E", "+55", 11900000002, "other.e2e@example.com")):
            await conn.execute(text(
                'INSERT INTO "user"."user" (id, names, lastnames, email, role, is_agent, code_phone, phone, '
                'document_type, document_number, deleted, enable) VALUES '
                "(:id, :n, 'Sintético', :e, 'client', false, :cp, :p, 'dni', :doc, false, true)"),
                {"id": uid, "n": names, "e": email, "cp": code_phone, "p": phone, "doc": str(phone)[-8:]})
        bank_id, tax_id, com_id = uuid4(), uuid4(), uuid4()
        await conn.execute(text(
            "INSERT INTO transaction.banks (id, bank, company, country, currency) "
            "VALUES (:i, 'BANCO E2E', 'Brasper E2E', 'pe', 'pen')"), {"i": bank_id})
        await conn.execute(text("INSERT INTO coin.tax_rate (id, coin_a, coin_b) VALUES (:i, 'pen', 'brl')"),
                           {"i": tax_id})
        await conn.execute(text("INSERT INTO coin.commission (id, coin_a, coin_b) VALUES (:i, 'pen', 'brl')"),
                           {"i": com_id})
        n = 0
        for uid, ops in ((OWNER_ID, OWNER_OPS + [OWNER_DELETED_OP]), (OTHER_ID, OTHER_OPS)):
            account_id = uuid4()
            await conn.execute(text(
                "INSERT INTO transaction.bank_accounts (id, user_id, bank_id, account_flow, account_holder_type, "
                "bank_country) VALUES (:i, :u, :b, 'destination', 'naturalPerson', 'pe')"),
                {"i": account_id, "u": uid, "b": bank_id})
            for code, status in ops:
                n += 1
                await conn.execute(text(
                    "INSERT INTO transaction.transactions (id, user_id, bank_account_destination_id, tax_rate_id, "
                    "commission_id, status, origin_amount, destination_amount, code, deleted, created_at, updated_at) "
                    "VALUES (:i, :u, :a, :t, :c, CAST(:s AS transaction.transaction_status), 100, 30, :code, :d, "
                    "now() - make_interval(mins => :age), now() - make_interval(mins => :age))"),
                    {"i": uuid4(), "u": uid, "a": account_id, "t": tax_id, "c": com_id, "s": status,
                     "code": code, "d": code == OWNER_DELETED_OP[0], "age": 100 - n})


async def seed_service_account(engine) -> None:
    """Cuenta de servicio del bot con contraseña hasheada por el código real del API."""
    username = os.environ.get("E2E_SERVICE_USERNAME", "")
    password = os.environ.get("E2E_SERVICE_PASSWORD", "")
    if not username or not password:
        return
    from sqlalchemy import text
    from app.core.security import SecurityUtils
    from app.core.settings import get_settings
    hashed = SecurityUtils(get_settings()).hash_password(password)
    auth_id = uuid4()
    async with engine.begin() as conn:
        if (await conn.execute(text('SELECT 1 FROM "user"."user" WHERE id=:i'), {"i": SERVICE_ID})).first():
            return
        await conn.execute(text('INSERT INTO "user".auth_login (id, username, password, must_change_password) '
                                "VALUES (:i, :u, :p, false)"), {"i": auth_id, "u": username, "p": hashed})
        await conn.execute(text(
            'INSERT INTO "user"."user" (id, auth_id, names, lastnames, email, role, is_agent, deleted, enable) '
            "VALUES (:id, :a, 'Servicio', 'Brasper IA E2E', 'svc.e2e@example.com', 'user', false, false, true)"),
            {"id": SERVICE_ID, "a": auth_id})


def build_control_app(engine, secret: str):
    import hmac
    from fastapi import Depends, FastAPI, Header, HTTPException
    from sqlalchemy import text

    def guard(x_e2e_control: str | None = Header(None)):
        if not x_e2e_control or not hmac.compare_digest(x_e2e_control, secret):
            raise HTTPException(401, "control e2e no autorizado")

    control = FastAPI(dependencies=[Depends(guard)])
    state = {"server": None}

    @control.get("/__e2e/seed")
    async def seed_info():
        return {"owner_id": str(OWNER_ID), "other_id": str(OTHER_ID),
                "owner_ops": OWNER_OPS, "owner_deleted_op": OWNER_DELETED_OP, "other_ops": OTHER_OPS}

    @control.get("/__e2e/links")
    async def links(user_id: UUID):
        async with engine.connect() as conn:
            rows = (await conn.execute(text(
                "SELECT channel, consumed_at IS NOT NULL AS consumed, deleted, expires_at < now() AS token_expired, "
                "grant_expires_at IS NOT NULL AND grant_expires_at < now() AS grant_expired "
                'FROM "user".ai_identity_links WHERE user_id=:u ORDER BY created_at'), {"u": user_id})).mappings().all()
            return [dict(r) for r in rows]

    @control.post("/__e2e/links/expire-tokens")
    async def expire_tokens(user_id: UUID):
        async with engine.begin() as conn:
            res = await conn.execute(text(
                "UPDATE \"user\".ai_identity_links SET expires_at = now() - interval '1 minute' "
                "WHERE user_id=:u AND consumed_at IS NULL"), {"u": user_id})
            return {"updated": res.rowcount}

    @control.post("/__e2e/links/expire-grants")
    async def expire_grants(user_id: UUID):
        async with engine.begin() as conn:
            res = await conn.execute(text(
                "UPDATE \"user\".ai_identity_links SET grant_expires_at = now() - interval '1 minute' "
                "WHERE user_id=:u AND consumed_at IS NOT NULL"), {"u": user_id})
            return {"updated": res.rowcount}

    @control.get("/__e2e/audit")
    async def audit():
        async with engine.connect() as conn:
            exists = (await conn.execute(text("SELECT to_regclass('audit.audit_event')"))).scalar()
            if not exists:
                return {"rows": None}
            rows = (await conn.execute(text(
                "SELECT action, description FROM audit.audit_event ORDER BY created_at"))).all()
            return {"rows": [list(r) for r in rows]}

    @control.get("/__e2e/service/stats")
    async def service_stats():
        async with engine.connect() as conn:
            ok = (await conn.execute(text("SELECT count(*) FROM audit.login_event WHERE user_id=:u AND success"),
                                     {"u": SERVICE_ID})).scalar()
            failed = (await conn.execute(text("SELECT count(*) FROM audit.login_event WHERE NOT success"))).scalar()
            active = (await conn.execute(text(
                'SELECT count(*) FROM "user".auth_session WHERE user_id=:u AND revoked_at IS NULL '
                "AND expires_at > now()"), {"u": SERVICE_ID})).scalar()
            total = (await conn.execute(text('SELECT count(*) FROM "user".auth_session WHERE user_id=:u'),
                                        {"u": SERVICE_ID})).scalar()
            return {"logins_ok": ok, "logins_failed": failed, "sessions_active": active, "sessions_total": total}

    @control.post("/__e2e/service/revoke-sessions")
    async def service_revoke():
        async with engine.begin() as conn:
            res = await conn.execute(text(
                "UPDATE \"user\".auth_session SET revoked_at=now(), revoke_reason='e2e', updated_at=now() "
                "WHERE user_id=:u AND revoked_at IS NULL"), {"u": SERVICE_ID})
            return {"revoked": res.rowcount}

    @control.post("/__e2e/service/enable")
    async def service_enable(value: bool):
        async with engine.begin() as conn:
            await conn.execute(text('UPDATE "user"."user" SET enable=:v WHERE id=:u'), {"v": value, "u": SERVICE_ID})
            return {"enable": value}

    @control.post("/__e2e/shutdown")
    async def shutdown():
        if state["server"] is not None:
            state["server"].should_exit = True
        return {"stopping": True}

    control.state.e2e = state
    return control


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pg-port", type=int, default=55450)
    parser.add_argument("--port", type=int, default=8010)
    args = parser.parse_args()
    secret = os.environ.get("E2E_SHARED_SECRET", "")
    if len(secret) < 24:
        print("E2E_SHARED_SECRET sintético (>=24 caracteres) es obligatorio", file=sys.stderr)
        return 2
    auth_required = os.environ.get("E2E_AUTH_REQUIRED", "1") != "0"
    outer, control = build_app(args.pg_port, secret, auth_required)

    import uvicorn
    config = uvicorn.Config(outer, host="127.0.0.1", port=args.port, log_level="warning",
                            lifespan="on", loop="asyncio", workers=1)
    server = uvicorn.Server(config)
    control.state.e2e["server"] = server
    thread = threading.Thread(target=server.run, name="uvicorn-e2e", daemon=True)
    thread.start()
    print(f"[e2e-api] escuchando en http://127.0.0.1:{args.port} (PGlite :{args.pg_port}, "
          f"AUTH_REQUIRED={auth_required})", flush=True)
    try:
        while thread.is_alive():
            thread.join(0.5)
    except KeyboardInterrupt:
        server.should_exit = True
        thread.join(10)
    print("[e2e-api] detenido", flush=True)
    # La conexión a PGlite puede colgar al cerrar: se sale sin esperar al pool.
    os._exit(0)


if __name__ == "__main__":
    sys.exit(main())
