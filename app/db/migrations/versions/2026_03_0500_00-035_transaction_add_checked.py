"""transaction_add_checked

Revision ID: 035
Revises: 034
Create Date: 2026-03-05

Añade columna checked (boolean) a transactions para checklist.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "035"
down_revision: Union[str, None] = "034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "transaction"


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("checked", sa.Boolean(), nullable=False, server_default=sa.false()),
        schema=schema,
    )
    op.create_index(
        op.f("ix_transaction_transactions_checked"),
        "transactions",
        ["checked"],
        schema=schema,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_transaction_transactions_checked"),
        table_name="transactions",
        schema=schema,
    )
    op.drop_column("transactions", "checked", schema=schema)
