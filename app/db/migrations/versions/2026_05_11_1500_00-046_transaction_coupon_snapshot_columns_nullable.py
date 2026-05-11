"""transaction_coupon_snapshot_columns_nullable

Revision ID: 046
Revises: 045
Create Date: 2026-05-11

Agrega como NULLABLE los campos de snapshot del cupón en transaction.transactions.
Estos campos son requeridos por el ORM/DTO actuales (coupon_discount_code, etc).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "046"
down_revision: Union[str, None] = "045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "transaction"
table = "transactions"


def _column_exists(conn, column_name: str) -> bool:
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
        {"schema": schema, "table": table, "column": column_name},
    ).fetchone()
    return row is not None


def upgrade() -> None:
    conn = op.get_bind()

    columns_to_add: list[tuple[str, sa.types.TypeEngine]] = [
        ("coupon_discount_code", sa.String(length=50)),
        ("coupon_origin_amount", sa.Numeric(20, 8)),
        ("coupon_destination_amount", sa.Numeric(20, 8)),
        ("coupon_discount_percentage", sa.Numeric(10, 4)),
        ("coupon_discount_commission", sa.Numeric(20, 8)),
        ("coupon_discount_total_to_send", sa.Numeric(20, 8)),
    ]

    for column_name, column_type in columns_to_add:
        if not _column_exists(conn, column_name):
            op.add_column(
                table,
                sa.Column(column_name, column_type, nullable=True),
                schema=schema,
            )


def downgrade() -> None:
    conn = op.get_bind()

    columns_to_drop = [
        "coupon_discount_code",
        "coupon_origin_amount",
        "coupon_destination_amount",
        "coupon_discount_percentage",
        "coupon_discount_commission",
        "coupon_discount_total_to_send",
    ]

    for column_name in columns_to_drop:
        if _column_exists(conn, column_name):
            op.drop_column(table, column_name, schema=schema)

