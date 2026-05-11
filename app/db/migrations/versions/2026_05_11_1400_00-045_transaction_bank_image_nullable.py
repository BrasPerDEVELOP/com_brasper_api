"""transaction_bank_image_nullable

Revision ID: 045
Revises: 044
Create Date: 2026-05-11

Asegura que transaction.banks.image sea NULLABLE.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "045"
down_revision: Union[str, None] = "044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "transaction"
table = "banks"
column = "image"


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

    # Si no existe o ya es NULLABLE, no hacemos nada.
    if row is None or row[0] == "YES":
        return

    op.alter_column(
        table,
        column,
        existing_type=sa.String(length=255),
        nullable=True,
        schema=schema,
    )


def downgrade() -> None:
    # Solo revertimos a NOT NULL si no hay filas con NULL en image.
    conn = op.get_bind()
    null_count = conn.execute(
        sa.text(
            """
            SELECT COUNT(1)
            FROM transaction.banks
            WHERE image IS NULL
            """
        )
    ).scalar()

    if not null_count:
        op.alter_column(
            table,
            column,
            existing_type=sa.String(length=255),
            nullable=False,
            schema=schema,
        )

