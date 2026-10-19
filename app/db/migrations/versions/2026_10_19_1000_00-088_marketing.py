"""Persistent marketing campaigns, delivery outbox and opt-outs."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "088"
down_revision = "087"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("marketing_campaigns",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("marketing_recipients",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_id", UUID(as_uuid=True), sa.ForeignKey("marketing_campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error", sa.String(250)),
        sa.Column("attempted_at", sa.DateTime(timezone=True)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("campaign_id", "email"))
    op.create_index("ix_marketing_queue", "marketing_recipients", ["status", "campaign_id"])
    op.create_table("marketing_suppressions",
        sa.Column("email", sa.String(254), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))


def downgrade():
    op.drop_table("marketing_suppressions")
    op.drop_table("marketing_recipients")
    op.drop_table("marketing_campaigns")
