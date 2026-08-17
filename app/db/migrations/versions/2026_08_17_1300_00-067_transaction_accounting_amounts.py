"""add accounting amounts to transaction.transactions

Revision ID: 067
Revises: 066
Create Date: 2026-08-17 13:00:00.000000

Agrega las columnas contables accounting_destination_amount,
accounting_commision y accounting_tax_final a transaction.transactions.
Nullable: las transacciones existentes no las tienen.
"""

from alembic import op
import sqlalchemy as sa

revision = "067"
down_revision = "066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("accounting_destination_amount", sa.Numeric(20, 8), nullable=True),
        schema="transaction",
    )
    op.add_column(
        "transactions",
        sa.Column("accounting_commision", sa.Numeric(20, 8), nullable=True),
        schema="transaction",
    )
    op.add_column(
        "transactions",
        sa.Column("accounting_tax_final", sa.Numeric(20, 8), nullable=True),
        schema="transaction",
    )


def downgrade() -> None:
    op.drop_column("transactions", "accounting_tax_final", schema="transaction")
    op.drop_column("transactions", "accounting_commision", schema="transaction")
    op.drop_column("transactions", "accounting_destination_amount", schema="transaction")
