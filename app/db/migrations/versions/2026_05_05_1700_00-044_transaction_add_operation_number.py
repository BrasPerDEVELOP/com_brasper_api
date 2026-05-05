"""transaction_add_operation_number

Revision ID: 044
Revises: 043
Create Date: 2026-05-05

Añade operation_number para registrar el número de operación de la transacción.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "044"
down_revision: Union[str, None] = "043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "transaction"
table = "transactions"
column = "operation_number"
index_name = "ix_transaction_transactions_operation_number"


def upgrade() -> None:
    conn = op.get_bind()
    row = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name = :table
              AND column_name = :column
            """
        ),
        {"schema": schema, "table": table, "column": column},
    ).fetchone()

    if row is None:
        op.add_column(
            table,
            sa.Column(column, sa.String(length=120), nullable=True),
            schema=schema,
        )

    idx = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = :schema
              AND tablename = :table
              AND indexname = :index_name
            """
        ),
        {"schema": schema, "table": table, "index_name": index_name},
    ).fetchone()

    if idx is None:
        op.create_index(index_name, table, [column], unique=False, schema=schema)


def downgrade() -> None:
    op.drop_index(index_name, table_name=table, schema=schema)
    op.drop_column(table, column, schema=schema)
