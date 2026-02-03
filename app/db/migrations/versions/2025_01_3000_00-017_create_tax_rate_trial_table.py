"""create_tax_rate_trial_table

Revision ID: 017
Revises: 016
Create Date: 2025-01-31

Crea tabla coin.tax_rate_trial (tasa prueba): misma estructura que tax_rate
(tax, coin_a, coin_b).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "coin"


def upgrade() -> None:
    op.execute(sa.text("""
        CREATE TABLE coin.tax_rate_trial (
            id UUID NOT NULL PRIMARY KEY,
            deleted BOOLEAN NOT NULL DEFAULT false,
            enable BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            created_by VARCHAR(250),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            tax NUMERIC(20, 8) NOT NULL DEFAULT 0,
            coin_a coin.currency NOT NULL,
            coin_b coin.currency NOT NULL
        )
    """))
    op.create_index(
        op.f("ix_coin_tax_rate_trial_coin_a"),
        "tax_rate_trial",
        ["coin_a"],
        schema=schema,
    )
    op.create_index(
        op.f("ix_coin_tax_rate_trial_coin_b"),
        "tax_rate_trial",
        ["coin_b"],
        schema=schema,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_coin_tax_rate_trial_coin_b"),
        table_name="tax_rate_trial",
        schema=schema,
    )
    op.drop_index(
        op.f("ix_coin_tax_rate_trial_coin_a"),
        table_name="tax_rate_trial",
        schema=schema,
    )
    op.drop_table("tax_rate_trial", schema=schema)
