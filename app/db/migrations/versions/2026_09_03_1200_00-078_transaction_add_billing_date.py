"""transaction_add_billing_date

Revision ID: 078
Revises: 077
Create Date: 2026-09-03

Agrega billing_date para registrar la fecha de facturación de la transacción.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "078"
down_revision: Union[str, None] = "077"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "transaction"
table = "transactions"
column = "billing_date"


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
            sa.Column(column, sa.DateTime(timezone=True), nullable=True),
            schema=schema,
        )


def downgrade() -> None:
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

    if row is not None:
        op.drop_column(table, column, schema=schema)
