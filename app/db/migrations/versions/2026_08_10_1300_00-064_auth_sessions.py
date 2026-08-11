"""create auth_session table for JWT refresh sessions

Revision ID: 064
Revises: 063
Create Date: 2026-08-10 13:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "064"
down_revision = "063"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "auth_session",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("refresh_token_hash", sa.String(64), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.auth_session.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rotation_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("client_app", sa.String(50), nullable=False, server_default="backoffice"),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(255), nullable=True),
        sa.Column("reuse_detected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "client_app IN ('backoffice', 'www')",
            name="ck_auth_session_client_app",
        ),
        schema="user",
    )
    op.create_index(
        "ix_user_auth_session_user_id",
        "auth_session",
        ["user_id"],
        schema="user",
    )
    op.create_index(
        "ix_user_auth_session_family_id",
        "auth_session",
        ["family_id"],
        schema="user",
    )
    op.create_index(
        "ix_user_auth_session_refresh_token_hash",
        "auth_session",
        ["refresh_token_hash"],
        unique=True,
        schema="user",
    )


def downgrade():
    op.drop_index("ix_user_auth_session_refresh_token_hash", table_name="auth_session", schema="user")
    op.drop_index("ix_user_auth_session_family_id", table_name="auth_session", schema="user")
    op.drop_index("ix_user_auth_session_user_id", table_name="auth_session", schema="user")
    op.drop_table("auth_session", schema="user")
