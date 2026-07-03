"""auth_token_and_auth_id_indexes

Revision ID: 056
Revises: 055
Create Date: 2026-07-02 13:00:00.000000

Índices para el camino caliente de autenticación. El TokenAuthMiddleware corre
en CADA request protegida y ejecuta:

    SELECT ... FROM "user".auth_login
    JOIN "user"."user" ON "user".auth_id = auth_login.id
    WHERE auth_login.token = :token

Sin índice en ``auth_login.token`` esto hace un seq scan de auth_login en cada
llamada; ``user.auth_id`` (columna del JOIN) tampoco estaba indexada. Estos
índices reducen la latencia de todas las peticiones autenticadas.

Se añade además ``user.role``, usado por los filtros de listado de usuarios y
por las comprobaciones de permisos.

Cambios puramente aditivos (crear índices): no alteran datos ni comportamiento
y son reversibles.

Nota: si en producción ``auth_login`` es grande y con mucho tráfico de escritura,
considera crear estos índices con ``CREATE INDEX CONCURRENTLY`` manualmente
(no cabe dentro de la transacción de Alembic).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "056"
down_revision: Union[str, None] = "055"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_user_auth_login_token",
        "auth_login",
        ["token"],
        unique=False,
        schema="user",
    )
    op.create_index(
        "ix_user_user_auth_id",
        "user",
        ["auth_id"],
        unique=False,
        schema="user",
    )
    op.create_index(
        "ix_user_user_role",
        "user",
        ["role"],
        unique=False,
        schema="user",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_user_role",
        table_name="user",
        schema="user",
    )
    op.drop_index(
        "ix_user_user_auth_id",
        table_name="user",
        schema="user",
    )
    op.drop_index(
        "ix_user_auth_login_token",
        table_name="auth_login",
        schema="user",
    )
