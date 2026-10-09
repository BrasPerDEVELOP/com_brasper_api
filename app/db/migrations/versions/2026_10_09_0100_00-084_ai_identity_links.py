"""One-time authenticated channel identity grants."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "084"
down_revision = "083"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("ai_identity_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.user.id"), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("subject_hash", sa.String(64), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("grant_hash", sa.String(64), unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("grant_expires_at", sa.DateTime(timezone=True)),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("enable", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by", sa.String(250)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), schema="user")
    op.create_index("ix_user_ai_identity_links_user_id", "ai_identity_links", ["user_id"], schema="user")


def downgrade():
    op.drop_table("ai_identity_links", schema="user")
