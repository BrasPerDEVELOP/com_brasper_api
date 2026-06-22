"""allow world cup coupons to target every exchange rate

Revision ID: 051
Revises: 050
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "051"
down_revision: Union[str, None] = "050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("coupons", "origin_currency", existing_type=sa.Enum(name="currency", schema="coin"), nullable=True, schema="transaction")
    op.alter_column("coupons", "destination_currency", existing_type=sa.Enum(name="currency", schema="coin"), nullable=True, schema="transaction")


def downgrade() -> None:
    op.execute(sa.text("""
        UPDATE transaction.coupons
        SET origin_currency = 'PEN', destination_currency = 'BRL'
        WHERE origin_currency IS NULL OR destination_currency IS NULL
    """))
    op.alter_column("coupons", "origin_currency", existing_type=sa.Enum(name="currency", schema="coin"), nullable=False, schema="transaction")
    op.alter_column("coupons", "destination_currency", existing_type=sa.Enum(name="currency", schema="coin"), nullable=False, schema="transaction")
