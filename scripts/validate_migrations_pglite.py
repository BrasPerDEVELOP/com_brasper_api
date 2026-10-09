"""Validación local de migraciones Alembic contra PGlite (PostgreSQL WASM).

Herramienta de laboratorio para máquinas donde no hay PostgreSQL nativo ni
Docker (p. ej. Windows con App Control bloqueando psycopg2). NO toca
producción: no importa ``app.core.settings`` ni lee ``.env``; usa un ``env.py``
propio (``scripts/pglite_alembic/env.py``) y las MISMAS versiones de
``app/db/migrations/versions``.

Requisitos:
  * Servidor PGlite por protocolo PG (``@electric-sql/pglite-socket``)::

        node node_modules/@electric-sql/pglite-socket/dist/scripts/server.js \
            --db=memory:// --port=55433

  * venv del API con ``asyncpg`` + ``sqlalchemy`` + ``alembic``.

Uso (desde la raíz de com_brasper_api)::

    python scripts/validate_migrations_pglite.py --port 55433 upgrade 082
    python scripts/validate_migrations_pglite.py --port 55433 seed
    python scripts/validate_migrations_pglite.py --port 55433 upgrade head
    python scripts/validate_migrations_pglite.py --port 55433 downgrade 083
    python scripts/validate_migrations_pglite.py --port 55433 snapshot out.json
    python scripts/validate_migrations_pglite.py --port 55433 dump backup_dir
    python scripts/validate_migrations_pglite.py --port 55434 restore backup_dir

Limitaciones: PGlite ejecuta UNA sola sesión de backend (todas las conexiones
del socket la comparten), así que esto NO prueba concurrencia ni bloqueos de
fila. Sólo se usa una conexión a la vez y nunca se reemplaza a una prueba en
PostgreSQL 16 real.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[1]
ENV_DIR = ROOT / "scripts" / "pglite_alembic"
VERSIONS_DIR = ROOT / "app" / "db" / "migrations" / "versions"

# Tablas financieras/identidad que se comparan con checksum en el drill.
FINANCIAL_TABLES = [
    "transaction.coupons",
    "transaction.transactions",
    "world_cup.coupon_redemptions",
    "transaction.coupon_campaign_versions",
    '"user".ai_identity_links',
    '"user"."user"',
]
USER_SCHEMAS_SQL = (
    "SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg\\_%' "
    "AND nspname <> 'information_schema' ORDER BY 1"
)


def make_engine(host: str, port: int, db: str):
    # Credenciales fijas del servidor PGlite local (no hay secretos reales).
    url = (
        f"postgresql+asyncpg://postgres:postgres@{host}:{port}/{db}"
        "?prepared_statement_cache_size=0"
    )
    return create_async_engine(
        url,
        poolclass=NullPool,
        isolation_level="AUTOCOMMIT",  # igual que app/db/migrations/env.py
        connect_args={"ssl": False, "statement_cache_size": 0},
    )


def alembic_config(sync_conn) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(ENV_DIR))
    cfg.set_main_option("version_locations", str(VERSIONS_DIR))
    cfg.set_main_option("path_separator", "os")
    cfg.attributes["connection"] = sync_conn
    return cfg


async def _close(conn) -> None:
    # Con PGlite el cierre a veces cuelga: se acota y se ignora.
    try:
        raw = await conn.get_raw_connection()
        raw.driver_connection.terminate()
        await conn.invalidate()
    except BaseException:  # noqa: BLE001
        pass


async def with_conn(args, fn):
    engine = make_engine(args.host, args.port, args.db)
    conn = await engine.connect()
    try:
        return await fn(conn)
    finally:
        await _close(conn)


# --------------------------------------------------------------------- alembic
async def run_alembic(args, action: str, rev: str):
    def _do(sync_conn):
        cfg = alembic_config(sync_conn)
        if action == "upgrade":
            command.upgrade(cfg, rev)
        elif action == "downgrade":
            command.downgrade(cfg, rev)
        else:
            command.current(cfg, verbose=False)

    async def go(conn):
        await conn.run_sync(_do)
        v = await conn.execute(text("SELECT version_num FROM public.alembic_version"))
        return [r[0] for r in v]

    versions = await with_conn(args, go)
    print(json.dumps({"action": action, "target": rev, "alembic_version": versions}))


# ------------------------------------------------------------------- snapshot
SCHEMA_FINGERPRINT_SQL = {
    "columns": """
        SELECT table_schema||'.'||table_name||'.'||column_name||':'||data_type||
               ':'||is_nullable||':'||coalesce(column_default,'')
        FROM information_schema.columns
        WHERE table_schema NOT LIKE 'pg\\_%' AND table_schema <> 'information_schema'
        ORDER BY 1""",
    "indexes": """
        SELECT schemaname||'.'||indexname||' '||indexdef FROM pg_indexes
        WHERE schemaname NOT LIKE 'pg\\_%' AND schemaname <> 'information_schema'
        ORDER BY 1""",
    "constraints": """
        SELECT n.nspname||'.'||c.conrelid::regclass::text||'.'||c.conname||' '||
               pg_get_constraintdef(c.oid)
        FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace
        WHERE n.nspname NOT LIKE 'pg\\_%' AND n.nspname <> 'information_schema'
        ORDER BY 1""",
}


async def list_tables(conn) -> list[str]:
    rows = await conn.execute(text("""
        SELECT quote_ident(schemaname)||'.'||quote_ident(tablename)
        FROM pg_tables
        WHERE schemaname NOT LIKE 'pg\\_%' AND schemaname <> 'information_schema'
        ORDER BY 1"""))
    return [r[0] for r in rows]


async def table_columns(conn, table: str) -> list[str]:
    rows = await conn.execute(text(
        "SELECT attname FROM pg_attribute WHERE attrelid = CAST(:t AS regclass) "
        "AND attnum > 0 AND NOT attisdropped ORDER BY attnum"), {"t": table})
    return [r[0] for r in rows]


async def table_checksum(conn, table: str, columns: list[str] | None = None) -> dict:
    exists = await conn.execute(text("SELECT to_regclass(:t)"), {"t": table})
    if exists.scalar() is None:
        return {"exists": False}
    cols = columns or await table_columns(conn, table)
    proj = ", ".join('"' + c.replace('"', '""') + '"' for c in cols)
    # Orden determinista por la fila completa en JSON (independiente de PK).
    row = (await conn.execute(text(
        f"SELECT count(*), md5(coalesce(string_agg(j, E'\\n' ORDER BY j), '')) "
        f"FROM (SELECT row_to_json(t)::text AS j FROM (SELECT {proj} FROM {table}) t) s"
    ))).one()
    return {"exists": True, "rows": row[0], "md5": row[1], "columns": cols}


async def snapshot(conn, base: dict | None = None) -> dict:
    """Huella de esquema + count/md5 por tabla.

    Con ``base`` (otro snapshot) añade ``tables_on_base_columns``: el checksum
    calculado SÓLO con las columnas que la tabla tenía en ``base`` para probar
    que los datos preexistentes no cambiaron tras un upgrade/downgrade.
    """
    out: dict = {"schema": {}, "tables": {}}
    for key, sql in SCHEMA_FINGERPRINT_SQL.items():
        rows = [r[0] for r in await conn.execute(text(sql))]
        out["schema"][key] = rows
        out["schema"][key + "_md5"] = hashlib.md5("\n".join(rows).encode()).hexdigest()
    for t in await list_tables(conn):
        out["tables"][t] = await table_checksum(conn, t)
    if base:
        out["tables_on_base_columns"] = {}
        for t, meta in base["tables"].items():
            if not meta.get("exists") or t not in out["tables"]:
                continue
            out["tables_on_base_columns"][t] = {
                "base": {"rows": meta["rows"], "md5": meta["md5"]},
                "now": {k: v for k, v in (await table_checksum(conn, t, meta["columns"])).items() if k not in ("columns", "exists")},
            }
            out["tables_on_base_columns"][t]["equal"] = (
                out["tables_on_base_columns"][t]["base"] == out["tables_on_base_columns"][t]["now"])
    v = await conn.execute(text("SELECT version_num FROM public.alembic_version"))
    out["alembic_version"] = [r[0] for r in v]
    return out


def compare(a: dict, b: dict) -> dict:
    res: dict = {"alembic_version": [a["alembic_version"], b["alembic_version"]], "schema": {}, "tables": {}}
    for key in SCHEMA_FINGERPRINT_SQL:
        sa_, sb = set(a["schema"][key]), set(b["schema"][key])
        res["schema"][key] = {"equal": sa_ == sb, "only_in_a": sorted(sa_ - sb), "only_in_b": sorted(sb - sa_)}
    for t in sorted(set(a["tables"]) | set(b["tables"])):
        ma, mb = a["tables"].get(t), b["tables"].get(t)
        pa = {k: ma[k] for k in ("rows", "md5")} if ma and ma.get("exists") else None
        pb = {k: mb[k] for k in ("rows", "md5")} if mb and mb.get("exists") else None
        if pa != pb:
            res["tables"][t] = {"a": pa, "b": pb}
    res["identical_data"] = not res["tables"]
    res["identical_schema"] = all(v["equal"] for v in res["schema"].values())
    return res


# ------------------------------------------------------------- dump / restore
async def dump(conn, out_dir: Path) -> dict:
    """Backup lógico: versión alembic + filas de TODAS las tablas en JSON.

    El esquema se reconstruye con ``alembic upgrade <versión>`` en la instancia
    destino (las migraciones son la fuente del esquema) y luego se valida con
    la huella de catálogo de ``snapshot``.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"alembic_version": None, "tables": {}}
    v = await conn.execute(text("SELECT version_num FROM public.alembic_version"))
    manifest["alembic_version"] = [r[0] for r in v]
    for t in await list_tables(conn):
        if t == "public.alembic_version":
            continue
        rows = [r[0] for r in await conn.execute(
            text(f"SELECT row_to_json(x)::text FROM {t} x"))]
        fname = t.replace('"', "") + ".jsonl"
        (out_dir / fname).write_text("\n".join(rows), encoding="utf-8")
        manifest["tables"][t] = {"file": fname, "rows": len(rows),
                                 "checksum": await table_checksum(conn, t)}
    # Secuencias (serial/identity).
    seqs = await conn.execute(text("""
        SELECT quote_ident(schemaname)||'.'||quote_ident(sequencename), last_value
        FROM pg_sequences WHERE schemaname NOT LIKE 'pg\\_%'"""))
    manifest["sequences"] = {r[0]: r[1] for r in seqs}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


async def restore(conn, in_dir: Path) -> dict:
    manifest = json.loads((in_dir / "manifest.json").read_text(encoding="utf-8"))
    # Carga sin disparar FKs/triggers durante la copia (orden libre).
    await conn.execute(text("SET session_replication_role = replica"))
    loaded = {}
    try:
        for t, meta in manifest["tables"].items():
            raw = (in_dir / meta["file"]).read_text(encoding="utf-8")
            lines = [ln for ln in raw.split("\n") if ln]
            # Las semillas de las migraciones (roles, tags...) ya existen en el
            # destino: se reemplazan por el contenido exacto del backup.
            await conn.execute(text(f"DELETE FROM {t}"))
            if lines:
                payload = "[" + ",".join(lines) + "]"
                await conn.execute(
                    text(f"INSERT INTO {t} SELECT * FROM json_populate_recordset(NULL::{t}, CAST(:p AS json))"),
                    {"p": payload},
                )
            loaded[t] = len(lines)
    finally:
        await conn.execute(text("SET session_replication_role = origin"))
    for seq, last in (manifest.get("sequences") or {}).items():
        if last is not None:
            await conn.execute(text("SELECT setval(CAST(:s AS regclass), :v)"), {"s": seq, "v": last})
    return {"loaded": loaded}


# ---------------------------------------------------------------------- seed
SEED_FILE = ROOT / "scripts" / "pglite_alembic" / "seed_pre_083.sql"


async def run_sql_file(conn, path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    raw = await conn.get_raw_connection()
    # asyncpg acepta múltiples sentencias sin parámetros en execute().
    await raw.driver_connection.execute(sql)


# ----------------------------------------------------------------------- CLI
def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=55433)
    p.add_argument("--db", default="postgres")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("upgrade", "downgrade"):
        s = sub.add_parser(name)
        s.add_argument("rev")
    sub.add_parser("current")
    s = sub.add_parser("sql", help="ejecuta un archivo .sql (p. ej. la semilla)")
    s.add_argument("file", nargs="?", default=str(SEED_FILE))
    s = sub.add_parser("query", help="ejecuta una consulta y muestra filas JSON")
    s.add_argument("sql")
    s = sub.add_parser("snapshot")
    s.add_argument("out")
    s.add_argument("--base", help="snapshot previo para comparar datos con sus columnas")
    s = sub.add_parser("compare", help="compara dos snapshots (esquema + datos)")
    s.add_argument("a")
    s.add_argument("b")
    s = sub.add_parser("dump")
    s.add_argument("out_dir")
    s = sub.add_parser("restore")
    s.add_argument("in_dir")
    args = p.parse_args()

    if args.cmd in ("upgrade", "downgrade"):
        asyncio.run(run_alembic(args, args.cmd, args.rev))
    elif args.cmd == "current":
        asyncio.run(run_alembic(args, "current", ""))
    elif args.cmd == "sql":
        asyncio.run(with_conn(args, lambda c: run_sql_file(c, Path(args.file))))
        print(json.dumps({"sql": args.file, "ok": True}))
    elif args.cmd == "query":
        async def q(c):
            res = await c.execute(text(args.sql))
            return [list(map(str, r)) for r in res] if res.returns_rows else []
        for row in asyncio.run(with_conn(args, q)):
            print(" | ".join(row))
    elif args.cmd == "snapshot":
        base = json.loads(Path(args.base).read_text(encoding="utf-8")) if args.base else None
        snap = asyncio.run(with_conn(args, lambda c: snapshot(c, base)))
        Path(args.out).write_text(json.dumps(snap, indent=2), encoding="utf-8")
        summary = {"snapshot": args.out, "alembic_version": snap["alembic_version"],
                   "tables": len(snap["tables"])}
        if base:
            tb = snap["tables_on_base_columns"]
            summary["preserved_tables"] = sum(1 for v in tb.values() if v["equal"])
            summary["changed_tables"] = {t: v for t, v in tb.items() if not v["equal"]}
            summary["missing_tables"] = [t for t, m in base["tables"].items() if t not in snap["tables"]]
        print(json.dumps(summary, indent=1))
    elif args.cmd == "compare":
        print(json.dumps(compare(json.loads(Path(args.a).read_text(encoding="utf-8")),
                                 json.loads(Path(args.b).read_text(encoding="utf-8"))), indent=1))
    elif args.cmd == "dump":
        m = asyncio.run(with_conn(args, lambda c: dump(c, Path(args.out_dir))))
        print(json.dumps({"dump": args.out_dir, "alembic_version": m["alembic_version"],
                          "tables": len(m["tables"])}))
    elif args.cmd == "restore":
        r = asyncio.run(with_conn(args, lambda c: restore(c, Path(args.in_dir))))
        print(json.dumps(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
