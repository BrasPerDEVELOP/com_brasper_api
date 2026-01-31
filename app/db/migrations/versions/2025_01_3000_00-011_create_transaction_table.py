"""create_transaction_table

Revision ID: 011
Revises: 010
Create Date: 2025-01-30

Crea esquema transaction y tabla transactions (amount, currency, type, status, reference).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "transaction"


def upgrade() -> None:
    op.execute(sa.text(f'CREATE schema IF NOT EXISTS "{schema}"'))
    op.execute(sa.text(
        "CREATE TYPE transaction.transaction_type AS ENUM ('deposit', 'withdrawal', 'transfer')"
    ))
    op.execute(sa.text(
        "CREATE TYPE transaction.transaction_status AS ENUM ('pending', 'completed', 'failed')"
    ))
    op.execute(sa.text("""
        CREATE TABLE transaction.transactions (
            id UUID NOT NULL PRIMARY KEY,
            deleted BOOLEAN NOT NULL DEFAULT false,
            enable BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            created_by VARCHAR(250),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            amount NUMERIC(20, 8) NOT NULL,
            currency coin.currency NOT NULL,
            type transaction.transaction_type NOT NULL,
            status transaction.transaction_status NOT NULL DEFAULT 'pending',
            reference VARCHAR(255)
        )
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
    op.create_index(
        op.f("ix_transaction_transactions_status"),
        "transactions",
        ["status"],
        schema=schema,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_transaction_transactions_status"),
        table_name="transactions",
        schema=schema,
    )
    op.drop_index(
        op.f("ix_transaction_transactions_type"),
        table_name="transactions",
        schema=schema,
    )
    op.drop_index(
        op.f("ix_transaction_transactions_currency"),
        table_name="transactions",
        schema=schema,
    )
    op.drop_table("transactions", schema=schema)
    op.execute(sa.text("DROP TYPE IF EXISTS transaction.transaction_status CASCADE"))
    op.execute(sa.text("DROP TYPE IF EXISTS transaction.transaction_type CASCADE"))
    op.execute(sa.text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
