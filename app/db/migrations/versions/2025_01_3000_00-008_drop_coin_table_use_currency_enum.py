"""drop_coin_table_use_currency_enum

Revision ID: 008
Revises: 007
Create Date: 2025-01-30

Elimina tabla coin; las monedas pasan a ser un enum (Currency).
El esquema coin se mantiene para tax_rate.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "coin"


def upgrade() -> None:
    op.drop_index(
        op.f("ix_coin_coin_code"), table_name="coin", schema=schema
    )
    op.drop_table("coin", schema=schema)


def downgrade() -> None:
    op.execute(sa.text(f'CREATE schema IF NOT EXISTS "{schema}"'))
    op.create_table(
        "coin",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("enable", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(250), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("code", sa.String(3), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("symbol", sa.String(10), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id"),
        schema=schema,
    )
    op.create_index(
        op.f("ix_coin_coin_code"), "coin", ["code"], unique=True, schema=schema
    )
