"""transaction_bank_account_origin_nullable

Revision ID: 043
Revises: 042
Create Date: 2026-04-25

Asegura que transaction.transactions.bank_account_origin_id sea NULLABLE,
alineado con el modelo ORM (cuenta origen opcional).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "043"
down_revision: Union[str, None] = "042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "transaction"
table = "transactions"
column = "bank_account_origin_id"


def upgrade() -> None:
    conn = op.get_bind()
    row = conn.execute(
        sa.text(
            """
            SELECT is_nullable
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name = :table
              AND column_name = :column
            """
        ),
        {"schema": schema, "table": table, "column": column},
    ).fetchone()

    if row is None:
        return

    if row[0] == "NO":
        op.alter_column(
            table,
            column,
            existing_type=sa.UUID(),
            nullable=True,
            schema=schema,
        )


def downgrade() -> None:
    """No forzar NOT NULL: puede existir filas con origen nulo."""
    pass
