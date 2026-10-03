"""Permiso management.view (panel gerencial) para el rol accounting."""
from alembic import op
import sqlalchemy as sa

revision = "081"
down_revision = "080"
branch_labels = None
depends_on = None

PERMISSION = "management.view"
ROLES = ("accounting",)


def upgrade():
    conn = op.get_bind()
    for role in ROLES:
        conn.execute(
            sa.text(
                """
                UPDATE "user".role_permission
                SET permissions = permissions || CAST(:perm AS jsonb)
                WHERE role = :role
                  AND NOT (permissions @> CAST(:perm AS jsonb))
                """
            ),
            {"role": role, "perm": f'["{PERMISSION}"]'},
        )


def downgrade():
    conn = op.get_bind()
    for role in ROLES:
        conn.execute(
            sa.text(
                """
                UPDATE "user".role_permission
                SET permissions = permissions - :perm
                WHERE role = :role
                """
            ),
            {"role": role, "perm": PERMISSION},
        )
