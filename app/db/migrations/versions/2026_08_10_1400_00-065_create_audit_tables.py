"""create audit schema and audit_event, login_event tables

Revision ID: 065
Revises: 064
Create Date: 2026-08-10 14:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "065"
down_revision = "064"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS audit;")

    op.create_table(
        "audit_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_username", sa.String(255), nullable=True),
        sa.Column("actor_role", sa.String(50), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity", sa.String(100), nullable=False),
        sa.Column("entity_id", sa.String(255), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("old_values", postgresql.JSONB, nullable=True),
        sa.Column("new_values", postgresql.JSONB, nullable=True),
        sa.Column("source", sa.String(50), nullable=False, server_default="backoffice"),
        sa.Column("ip_address", postgresql.INET, nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("method", sa.String(10), nullable=True),
        sa.Column("path", sa.Text, nullable=True),
        sa.Column("status_code", sa.Integer, nullable=True),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("success", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("source IN ('backoffice', 'www', 'ia', 'system')", name="ck_audit_event_source"),
        schema="audit",
    )

    op.create_index("ix_audit_event_created_at", "audit_event", ["created_at"], schema="audit")
    op.create_index("ix_audit_event_actor_user_id_created_at", "audit_event", ["actor_user_id", "created_at"], schema="audit")
    op.create_index("ix_audit_event_entity_entity_id", "audit_event", ["entity", "entity_id"], schema="audit")
    op.create_index("ix_audit_event_action_created_at", "audit_event", ["action", "created_at"], schema="audit")
    op.create_index("ix_audit_event_source_created_at", "audit_event", ["source", "created_at"], schema="audit")
    op.create_index("ix_audit_event_request_id", "audit_event", ["request_id"], schema="audit")

    op.create_table(
        "login_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("attempted_username", sa.String(255), nullable=True),
        sa.Column("success", sa.Boolean, nullable=False),
        sa.Column("failure_reason", sa.String(255), nullable=True),
        sa.Column("ip_address", postgresql.INET, nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("browser", sa.String(100), nullable=True),
        sa.Column("os", sa.String(100), nullable=True),
        sa.Column("device", sa.String(100), nullable=True),
        sa.Column("source", sa.String(50), nullable=False, server_default="backoffice"),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.auth_session.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("source IN ('backoffice', 'www', 'ia', 'system')", name="ck_login_event_source"),
        schema="audit",
    )

    op.create_index("ix_login_event_created_at", "login_event", ["created_at"], schema="audit")
    op.create_index("ix_login_event_user_id_created_at", "login_event", ["user_id", "created_at"], schema="audit")
    op.create_index("ix_login_event_request_id", "login_event", ["request_id"], schema="audit")


def downgrade():
    op.drop_index("ix_login_event_request_id", table_name="login_event", schema="audit")
    op.drop_index("ix_login_event_user_id_created_at", table_name="login_event", schema="audit")
    op.drop_index("ix_login_event_created_at", table_name="login_event", schema="audit")
    op.drop_table("login_event", schema="audit")

    op.drop_index("ix_audit_event_request_id", table_name="audit_event", schema="audit")
    op.drop_index("ix_audit_event_source_created_at", table_name="audit_event", schema="audit")
    op.drop_index("ix_audit_event_action_created_at", table_name="audit_event", schema="audit")
    op.drop_index("ix_audit_event_entity_entity_id", table_name="audit_event", schema="audit")
    op.drop_index("ix_audit_event_actor_user_id_created_at", table_name="audit_event", schema="audit")
    op.drop_index("ix_audit_event_created_at", table_name="audit_event", schema="audit")
    op.drop_table("audit_event", schema="audit")

    op.execute("DROP SCHEMA IF EXISTS audit;")
