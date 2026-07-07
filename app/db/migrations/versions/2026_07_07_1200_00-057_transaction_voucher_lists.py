"""transaction_voucher_lists

Revision ID: 057
Revises: 056
Create Date: 2026-07-07 12:00:00.000000

Agrega columnas JSONB para almacenar multiples comprobantes por transaccion.
Las columnas string legacy se mantienen como primer archivo para compatibilidad.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "057"
down_revision: Union[str, None] = "056"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "transaction"
table = "transactions"


def upgrade() -> None:
    op.add_column(
        table,
        sa.Column("send_vouchers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema=schema,
    )
    op.add_column(
        table,
        sa.Column("payment_vouchers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema=schema,
    )
    op.add_column(
        table,
        sa.Column("checked_images", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema=schema,
    )
    op.execute(
        """
        UPDATE transaction.transactions
        SET send_vouchers = CASE
            WHEN send_voucher IS NOT NULL AND btrim(send_voucher) <> ''
            THEN jsonb_build_array(send_voucher)
            ELSE NULL
        END,
        payment_vouchers = CASE
            WHEN payment_voucher IS NOT NULL AND btrim(payment_voucher) <> ''
            THEN jsonb_build_array(payment_voucher)
            ELSE NULL
        END,
        checked_images = CASE
            WHEN checked_image IS NOT NULL AND btrim(checked_image) <> ''
            THEN jsonb_build_array(checked_image)
            ELSE NULL
        END
        """
    )


def downgrade() -> None:
    op.drop_column(table, "checked_images", schema=schema)
    op.drop_column(table, "payment_vouchers", schema=schema)
    op.drop_column(table, "send_vouchers", schema=schema)
