"""create coin.commission_accounting and link it from transaction.transactions

Revision ID: 066
Revises: 065
Create Date: 2026-08-17 12:00:00.000000

Crea la tabla coin.commission_accounting (misma estructura que coin.commission)
y agrega transaction.transactions.commission_accounting_id como FK nullable: las
transacciones existentes no tienen comisión contable asociada.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "066"
down_revision = "065"
branch_labels = None
depends_on = None

schema = "coin"


def upgrade() -> None:
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS coin.commission_accounting (
            id UUID NOT NULL PRIMARY KEY,
            deleted BOOLEAN NOT NULL DEFAULT false,
            enable BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            created_by VARCHAR(250),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            coin_a coin.currency NOT NULL,
            coin_b coin.currency NOT NULL,
            percentage NUMERIC(20, 8) NOT NULL DEFAULT 0,
            reverse NUMERIC(20, 8) NOT NULL DEFAULT 0,
            min_amount NUMERIC(20, 8) NULL,
            max_amount NUMERIC(20, 8) NULL
        )
    """))

    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_coin_commission_accounting_coin_a "
        "ON coin.commission_accounting (coin_a)"
    ))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_coin_commission_accounting_coin_b "
        "ON coin.commission_accounting (coin_b)"
    ))

    op.add_column(
        "transactions",
        sa.Column("commission_accounting_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema="transaction",
    )
    op.create_foreign_key(
        "fk_transactions_commission_accounting_id",
        "transactions",
        "commission_accounting",
        ["commission_accounting_id"],
        ["id"],
        source_schema="transaction",
        referent_schema=schema,
    )
    op.create_index(
        "ix_transaction_transactions_commission_accounting_id",
        "transactions",
        ["commission_accounting_id"],
        schema="transaction",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_transaction_transactions_commission_accounting_id",
        table_name="transactions",
        schema="transaction",
    )
    op.drop_constraint(
        "fk_transactions_commission_accounting_id",
        "transactions",
        schema="transaction",
        type_="foreignkey",
    )
    op.drop_column("transactions", "commission_accounting_id", schema="transaction")

    op.drop_index(
        "ix_coin_commission_accounting_coin_b",
        table_name="commission_accounting",
        schema=schema,
    )
    op.drop_index(
        "ix_coin_commission_accounting_coin_a",
        table_name="commission_accounting",
        schema=schema,
    )
    op.drop_table("commission_accounting", schema=schema)
