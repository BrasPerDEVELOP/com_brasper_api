"""Alembic env SOLO para validación local contra PGlite (no se usa en producción).

Replica el flujo ``run_migrations_online`` de ``app/db/migrations/env.py``
(esquemas ``user``/``blog``, ``public.alembic_version``, AUTOCOMMIT,
``search_path``, ``render_as_batch``) pero recibe una conexión síncrona ya
abierta en ``config.attributes["connection"]`` (obtenida con
``AsyncConnection.run_sync`` sobre asyncpg). No importa ``app.core.settings``,
así que no lee ``.env`` ni secretos. Lo invoca
``scripts/validate_migrations_pglite.py``.
"""
from alembic import context

config = context.config
connection = config.attributes.get("connection")
if connection is None:
    raise RuntimeError(
        "Este env.py sólo funciona vía scripts/validate_migrations_pglite.py "
        "(requiere config.attributes['connection'])."
    )

for sch in ('"user"', "blog"):
    connection.exec_driver_sql(f"CREATE SCHEMA IF NOT EXISTS {sch}")
connection.exec_driver_sql(
    "CREATE TABLE IF NOT EXISTS public.alembic_version ("
    " version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
)
connection.exec_driver_sql('SET search_path TO public, "user", "blog"')

context.configure(
    connection=connection,
    target_metadata=None,
    include_schemas=True,
    version_table_schema="public",
    compare_type=True,
    render_as_batch=True,
)
with context.begin_transaction():
    context.run_migrations()
