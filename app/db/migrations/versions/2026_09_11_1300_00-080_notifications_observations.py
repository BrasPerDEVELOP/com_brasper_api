"""Internal inbox and transaction observations."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "080"
down_revision = "079"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("transactions", sa.Column("observaciones", sa.Text()), schema="transaction")
    op.create_table("notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("recipient_user_id", UUID(as_uuid=True), sa.ForeignKey("user.user.id"), nullable=False),
        sa.Column("actor_user_id", UUID(as_uuid=True), sa.ForeignKey("user.user.id")),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.String(40)), sa.Column("entity_id", UUID(as_uuid=True)),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_notifications_inbox", "notifications", ["recipient_user_id", "created_at"])
    op.execute("""UPDATE "user".role_permission
        SET permissions = COALESCE(permissions, '[]'::jsonb) || '["notifications.view"]'::jsonb
        WHERE role IN ('admin', 'sales', 'accounting', 'marketing', 'user')
        AND NOT COALESCE(permissions, '[]'::jsonb) ? 'notifications.view'""")
    op.execute("""UPDATE "user".role_permission
        SET permissions = COALESCE(permissions, '[]'::jsonb) || '["notifications.create"]'::jsonb
        WHERE role = 'admin' AND NOT COALESCE(permissions, '[]'::jsonb) ? 'notifications.create'""")


def downgrade():
    op.execute("""UPDATE "user".role_permission
        SET permissions = permissions - 'notifications.view' - 'notifications.create'""")
    op.drop_table("notifications")
    op.drop_column("transactions", "observaciones", schema="transaction")
