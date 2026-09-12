"""User permissions inherited from roles with explicit deltas."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "079"
down_revision = "078"
branch_labels = None
depends_on = None


def upgrade():
    for name in ("permissions_granted", "permissions_revoked"):
        op.add_column("user", sa.Column(name, JSONB(), nullable=False,
                      server_default=sa.text("'[]'::jsonb")), schema="user")


def downgrade():
    for name in ("permissions_revoked", "permissions_granted"):
        op.drop_column("user", name, schema="user")
