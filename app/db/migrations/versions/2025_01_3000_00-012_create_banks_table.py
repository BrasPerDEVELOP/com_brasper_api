"""create_banks_table

Revision ID: 012
Revises: 011
Create Date: 2025-01-30

Crea tipo transaction.bank_country y tabla transaction.banks
(bank, account, pix, company, currency, image, country).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "transaction"


def upgrade() -> None:
    op.execute(sa.text(
        "CREATE TYPE transaction.bank_country AS ENUM ('pe', 'br')"
    ))
    op.execute(sa.text("""
        CREATE TABLE transaction.banks (
            id UUID NOT NULL PRIMARY KEY,
            deleted BOOLEAN NOT NULL DEFAULT false,
            enable BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            created_by VARCHAR(250),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            bank VARCHAR(120) NOT NULL,
            account VARCHAR(80),
            pix VARCHAR(80),
            company VARCHAR(200) NOT NULL,
            currency coin.currency NOT NULL,
            image VARCHAR(255) NOT NULL,
            country transaction.bank_country NOT NULL
        )
    """))
    op.create_index(
        op.f("ix_transaction_banks_bank"),
        "banks",
        ["bank"],
        schema=schema,
    )
    op.create_index(
        op.f("ix_transaction_banks_currency"),
        "banks",
        ["currency"],
        schema=schema,
    )
    op.create_index(
        op.f("ix_transaction_banks_country"),
        "banks",
        ["country"],
        schema=schema,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_transaction_banks_country"),
        table_name="banks",
        schema=schema,
    )
    op.drop_index(
        op.f("ix_transaction_banks_currency"),
        table_name="banks",
        schema=schema,
    )
    op.drop_index(
        op.f("ix_transaction_banks_bank"),
        table_name="banks",
        schema=schema,
    )
    op.drop_table("banks", schema=schema)
    op.execute(sa.text("DROP TYPE IF EXISTS transaction.bank_country CASCADE"))
