"""transaction_only_status

Revision ID: 014
Revises: 013
Create Date: 2025-01-30

Deja en transaction.transactions solo la columna status (elimina amount, currency, type, reference).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "transaction"


def upgrade() -> None:
    op.drop_index(
        op.f("ix_transaction_transactions_currency"),
        table_name="transactions",
        schema=schema,
    )
    op.drop_index(
        op.f("ix_transaction_transactions_type"),
        table_name="transactions",
        schema=schema,
    )
    op.drop_column("transactions", "reference", schema=schema)
    op.drop_column("transactions", "type", schema=schema)
    op.drop_column("transactions", "currency", schema=schema)
    op.drop_column("transactions", "amount", schema=schema)
    op.execute(sa.text("DROP TYPE IF EXISTS transaction.transaction_type CASCADE"))


def downgrade() -> None:
    op.execute(sa.text(
        "CREATE TYPE transaction.transaction_type AS ENUM ('deposit', 'withdrawal', 'transfer')"
    ))
    op.execute(sa.text("""
        ALTER TABLE transaction.transactions
        ADD COLUMN amount NUMERIC(20, 8),
        ADD COLUMN currency coin.currency,
        ADD COLUMN type transaction.transaction_type,
        ADD COLUMN reference VARCHAR(255)
    """))
    op.create_index(
        op.f("ix_transaction_transactions_currency"),
        "transactions",
        ["currency"],
        schema=schema,
    )
    op.create_index(
        op.f("ix_transaction_transactions_type"),
        "transactions",
        ["type"],
        schema=schema,
    )
