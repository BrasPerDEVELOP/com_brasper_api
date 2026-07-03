"""add_metrics_permissions

Revision ID: 054
Revises: 053
Create Date: 2026-07-01 12:00:00.000000

Añade el permiso ``metrics.view`` a los roles admin, sales y accounting.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "054"
down_revision: Union[str, None] = "053"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    # Añade metrics.view sin duplicar si ya estuviera presente.
    conn.execute(sa.text("""
        UPDATE "user".role_permission
        SET permissions = permissions || '["metrics.view"]'::jsonb
        WHERE role IN ('admin', 'sales', 'accounting')
          AND NOT (permissions @> '["metrics.view"]'::jsonb)
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE "user".role_permission
        SET permissions = permissions - 'metrics.view'
        WHERE role IN ('admin', 'sales', 'accounting')
    """))
