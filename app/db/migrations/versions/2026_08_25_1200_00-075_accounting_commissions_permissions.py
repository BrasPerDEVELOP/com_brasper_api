"""accounting_commissions_permissions

Revision ID: 075
Revises: 074
Create Date: 2026-08-25

Da al rol contabilidad acceso completo a comisiones.
"""

from typing import Sequence, Union
import json

import sqlalchemy as sa
from alembic import op

revision: str = "075"
down_revision: Union[str, None] = "074"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "user"

accounting_permissions = [
    "commissions.view",
    "commissions.create",
    "commissions.update",
    "commissions.delete",
]


def _table_exists(conn, table: str) -> bool:
    row = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = :schema
              AND table_name = :table
            """
        ),
        {"schema": schema, "table": table},
    ).fetchone()
    return row is not None


def upgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, "role_permission"):
        return

    conn.execute(
        sa.text(
            """
            UPDATE "user".role_permission
            SET permissions = (
                SELECT jsonb_agg(permission ORDER BY permission)
                FROM (
                    SELECT DISTINCT jsonb_array_elements_text(permissions) AS permission
                    UNION
                    SELECT jsonb_array_elements_text(CAST(:extra_permissions AS jsonb)) AS permission
                ) AS merged
            ),
            updated_at = now()
            WHERE role = 'accounting'
              AND deleted IS false
            """
        ),
        {"extra_permissions": json.dumps(accounting_permissions)},
    )


def downgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, "role_permission"):
        return

    conn.execute(
        sa.text(
            """
            UPDATE "user".role_permission
            SET permissions = (
                SELECT COALESCE(jsonb_agg(permission ORDER BY permission), '[]'::jsonb)
                FROM (
                    SELECT jsonb_array_elements_text(permissions) AS permission
                    EXCEPT
                    SELECT jsonb_array_elements_text(CAST(:extra_permissions AS jsonb)) AS permission
                ) AS pruned
            ),
            updated_at = now()
            WHERE role = 'accounting'
              AND deleted IS false
            """
        ),
        {"extra_permissions": json.dumps(accounting_permissions)},
    )
