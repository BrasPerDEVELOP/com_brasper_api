"""create_coupons_table

Revision ID: 016
Revises: 015
Create Date: 2025-01-31

Crea tabla transaction.coupons (code, discount_percentage, max_uses,
origin_currency, destination_currency, start_date, end_date, is_active).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "transaction"


def upgrade() -> None:
    op.execute(sa.text("""
        CREATE TABLE transaction.coupons (
            id UUID NOT NULL PRIMARY KEY,
            deleted BOOLEAN NOT NULL DEFAULT false,
            enable BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            created_by VARCHAR(250),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            code VARCHAR(80) NOT NULL UNIQUE,
            discount_percentage NUMERIC(10, 4) NOT NULL,
            max_uses INTEGER NOT NULL,
            origin_currency coin.currency NOT NULL,
            destination_currency coin.currency NOT NULL,
            start_date TIMESTAMP WITH TIME ZONE,
            end_date TIMESTAMP WITH TIME ZONE,
            is_active BOOLEAN NOT NULL DEFAULT true
        )
    """))
    op.create_index(
        op.f("ix_transaction_coupons_code"),
        "coupons",
        ["code"],
        schema=schema,
    )
    op.create_index(
        op.f("ix_transaction_coupons_origin_currency"),
        "coupons",
        ["origin_currency"],
        schema=schema,
    )
    op.create_index(
        op.f("ix_transaction_coupons_destination_currency"),
        "coupons",
        ["destination_currency"],
        schema=schema,
    )
    op.create_index(
        op.f("ix_transaction_coupons_is_active"),
        "coupons",
        ["is_active"],
        schema=schema,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_transaction_coupons_is_active"),
        table_name="coupons",
        schema=schema,
    )
    op.drop_index(
        op.f("ix_transaction_coupons_destination_currency"),
        table_name="coupons",
        schema=schema,
    )
    op.drop_index(
        op.f("ix_transaction_coupons_origin_currency"),
        table_name="coupons",
        schema=schema,
    )
    op.drop_index(
        op.f("ix_transaction_coupons_code"),
        table_name="coupons",
        schema=schema,
    )
    op.drop_table("coupons", schema=schema)
