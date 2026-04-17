"""transaction_add_agent_id

Revision ID: 040
Revises: 039
Create Date: 2026-04-17

Añade columna agent_id opcional a transaction.transactions.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "040"
down_revision: Union[str, None] = "039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "transaction"


def upgrade() -> None:
    conn = op.get_bind()

    column_exists = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name = 'transactions'
              AND column_name = 'agent_id'
            """
        ),
        {"schema": schema},
    ).fetchone()

    if column_exists is None:
        op.add_column(
            "transactions",
            sa.Column("agent_id", sa.UUID(), nullable=True),
            schema=schema,
        )

    constraint_exists = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.table_constraints
            WHERE table_schema = :schema
              AND table_name = 'transactions'
              AND constraint_name = 'fk_transactions_agent_id_user'
            """
        ),
        {"schema": schema},
    ).fetchone()

    if constraint_exists is None:
        op.create_foreign_key(
            "fk_transactions_agent_id_user",
            "transactions",
            "user",
            ["agent_id"],
            ["id"],
            source_schema=schema,
            referent_schema="user",
        )

    index_exists = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = :schema
              AND tablename = 'transactions'
              AND indexname = 'ix_transaction_transactions_agent_id'
            """
        ),
        {"schema": schema},
    ).fetchone()

    if index_exists is None:
        op.create_index(
            op.f("ix_transaction_transactions_agent_id"),
            "transactions",
            ["agent_id"],
            schema=schema,
        )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_transaction_transactions_agent_id"),
        table_name="transactions",
        schema=schema,
    )
    op.drop_constraint(
        "fk_transactions_agent_id_user",
        "transactions",
        schema=schema,
        type_="foreignkey",
    )
    op.drop_column("transactions", "agent_id", schema=schema)
