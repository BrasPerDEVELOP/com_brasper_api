"""transaction_multiple_destinations

Revision ID: 059
Revises: 058
Create Date: 2026-07-13 12:00:00.000000

Normaliza la distribución del monto destino. Cada registro existente recibe
una distribución única equivalente a sus campos legacy.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "059"
down_revision: Union[str, None] = "058"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "transaction"
table = "transaction_destinations"


def upgrade() -> None:
    op.create_table(
        table,
        sa.Column("transaction_id", sa.UUID(), nullable=False),
        sa.Column("bank_account_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.String(length=250), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transaction.transactions.id"],
            name="fk_transaction_destinations_transaction_id_transactions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["bank_account_id"],
            ["transaction.bank_accounts.id"],
            name="fk_transaction_destinations_bank_account_id_bank_accounts",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_transaction_destinations"),
        sa.UniqueConstraint(
            "transaction_id",
            "bank_account_id",
            name="uq_transaction_destinations_transaction_account",
        ),
        schema=schema,
    )
    op.create_index(
        op.f("ix_transaction_transaction_destinations_transaction_id"),
        table,
        ["transaction_id"],
        schema=schema,
    )
    op.create_index(
        op.f("ix_transaction_transaction_destinations_bank_account_id"),
        table,
        ["bank_account_id"],
        schema=schema,
    )
    op.execute(
        sa.text(
            """
            INSERT INTO transaction.transaction_destinations
                (id, transaction_id, bank_account_id, amount, position,
                 deleted, enable, created_at, updated_at)
            SELECT id, id, bank_account_destination_id,
                   destination_amount, 0, false, true, created_at, updated_at
            FROM transaction.transactions
            WHERE deleted = false
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_transaction_transaction_destinations_bank_account_id"),
        table_name=table,
        schema=schema,
    )
    op.drop_index(
        op.f("ix_transaction_transaction_destinations_transaction_id"),
        table_name=table,
        schema=schema,
    )
    op.drop_table(table, schema=schema)
