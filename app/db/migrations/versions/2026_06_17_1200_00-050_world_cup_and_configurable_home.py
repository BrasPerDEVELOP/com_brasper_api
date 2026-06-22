"""world cup campaign

Revision ID: 050
Revises: 049
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "050"
down_revision: Union[str, None] = "049"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text('CREATE SCHEMA IF NOT EXISTS "world_cup"'))
    op.create_table(
        "matches",
        sa.Column("provider_id", sa.String(80), nullable=False),
        sa.Column("stage", sa.String(100), nullable=True),
        sa.Column("home_team", sa.String(120), nullable=False),
        sa.Column("away_team", sa.String(120), nullable=False),
        sa.Column("home_team_code", sa.String(10), nullable=True),
        sa.Column("away_team_code", sa.String(10), nullable=True),
        sa.Column("home_score", sa.Integer(), nullable=True),
        sa.Column("away_score", sa.Integer(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="SCHEDULED"),
        sa.Column("selected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(250), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_id", name="uq_world_cup_match_provider_id"),
        schema="world_cup",
    )
    op.create_index("ix_world_cup_matches_starts_at", "matches", ["starts_at"], schema="world_cup")
    op.create_index("ix_world_cup_matches_status", "matches", ["status"], schema="world_cup")

    op.create_table(
        "campaign",
        sa.Column("name", sa.String(120), nullable=False, server_default="Mundial 2026"),
        sa.Column("mode", sa.String(20), nullable=False, server_default="REVIEW"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("default_discount_percentage", sa.Numeric(10, 4), nullable=False, server_default="10"),
        sa.Column("default_max_uses", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("default_per_user_limit", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("origin_currency", sa.String(10), nullable=False, server_default="PEN"),
        sa.Column("destination_currency", sa.String(10), nullable=False, server_default="BRL"),
        sa.Column("code_template", sa.String(80), nullable=False, server_default="MUNDIAL-{HOME}-{AWAY}"),
        sa.Column("notification_emails", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(250), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        schema="world_cup",
    )

    op.add_column("coupons", sa.Column("coupon_type", sa.String(20), nullable=False, server_default="STANDARD"), schema="transaction")
    op.add_column("coupons", sa.Column("lifecycle_status", sa.String(30), nullable=False, server_default="ACTIVE"), schema="transaction")
    op.add_column("coupons", sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"), schema="transaction")
    op.add_column("coupons", sa.Column("per_user_limit", sa.Integer(), nullable=True), schema="transaction")
    op.add_column("coupons", sa.Column("match_id", postgresql.UUID(as_uuid=True), nullable=True), schema="transaction")
    op.create_foreign_key("fk_coupon_world_cup_match", "coupons", "matches", ["match_id"], ["id"], source_schema="transaction", referent_schema="world_cup", ondelete="SET NULL")
    op.create_index("ix_transaction_coupons_match_id", "coupons", ["match_id"], schema="transaction")

    op.create_table(
        "coupon_redemptions",
        sa.Column("coupon_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(250), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["coupon_id"], ["transaction.coupons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["transaction_id"], ["transaction.transactions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        schema="world_cup",
    )
    op.create_index("ix_coupon_redemptions_coupon_user", "coupon_redemptions", ["coupon_id", "user_id"], schema="world_cup")

    op.create_table(
        "notifications",
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("message", sa.String(1000), nullable=False),
        sa.Column("match_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("email_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dedupe_key", sa.String(180), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(250), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["match_id"], ["world_cup.matches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key", name="uq_world_cup_notification_dedupe"),
        schema="world_cup",
    )
    op.execute(sa.text("""
        UPDATE "user".role_permission
        SET permissions = permissions || '["world_cup.view", "world_cup.manage", "world_cup.approve"]'::jsonb
        WHERE role IN ('admin', 'marketing')
    """))


def downgrade() -> None:
    op.execute(sa.text("""
        UPDATE "user".role_permission
        SET permissions = permissions - 'world_cup.view' - 'world_cup.manage' - 'world_cup.approve'
        WHERE role IN ('admin', 'marketing')
    """))
    op.drop_table("notifications", schema="world_cup")
    op.drop_table("coupon_redemptions", schema="world_cup")
    op.drop_index("ix_transaction_coupons_match_id", table_name="coupons", schema="transaction")
    op.drop_constraint("fk_coupon_world_cup_match", "coupons", schema="transaction", type_="foreignkey")
    for column in ["match_id", "per_user_limit", "used_count", "lifecycle_status", "coupon_type"]:
        op.drop_column("coupons", column, schema="transaction")
    op.drop_table("campaign", schema="world_cup")
    op.drop_table("matches", schema="world_cup")
    op.execute(sa.text('DROP SCHEMA IF EXISTS "world_cup" CASCADE'))
