"""commission_min_max_amount

Revision ID: 010
Revises: 009
Create Date: 2025-01-30

Añade min_amount y max_amount a coin.commission.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "coin"
table = "commission"


def upgrade() -> None:
    op.add_column(
        table,
        sa.Column("min_amount", sa.Numeric(20, 8), nullable=True),
        schema=schema,
    )
    op.add_column(
        table,
        sa.Column("max_amount", sa.Numeric(20, 8), nullable=True),
        schema=schema,
    )


def downgrade() -> None:
    op.drop_column(table, "max_amount", schema=schema)
    op.drop_column(table, "min_amount", schema=schema)
