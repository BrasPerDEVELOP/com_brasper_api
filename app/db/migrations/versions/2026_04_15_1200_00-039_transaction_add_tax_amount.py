"""transaction_add_tax_amount

Revision ID: 039
Revises: 038
Create Date: 2026-04-15

Añade columna tax_amount (monto de impuesto) a transaction.transactions.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "039"
down_revision: Union[str, None] = "038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "transaction"


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("tax_amount", sa.Numeric(20, 8), nullable=True),
        schema=schema,
    )


def downgrade() -> None:
    op.drop_column("transactions", "tax_amount", schema=schema)
