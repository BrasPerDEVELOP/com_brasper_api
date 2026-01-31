"""transaction_fks_and_fields

Revision ID: 015
Revises: 014
Create Date: 2025-01-30

Añade a transaction.transactions: bank_account_id, user_id, tax_rate_id, commission_id,
origin_amount, destination_amount, code, send_date, payment_date, send_voucher, payment_voucher.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "transaction"
coin_schema = "coin"


def upgrade() -> None:
    # Crear coin.tax_rate si no existe (nunca hubo migración que la creara)
    op.execute(sa.text(f'CREATE schema IF NOT EXISTS "{coin_schema}"'))
    op.execute(sa.text(
        "DO $$ BEGIN CREATE TYPE coin.currency AS ENUM ('pen', 'brl', 'usd'); EXCEPTION WHEN duplicate_object THEN null; END $$"
    ))
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS coin.tax_rate (
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
    op.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS ix_coin_tax_rate_coin_a ON coin.tax_rate (coin_a)
    """))
    op.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS ix_coin_tax_rate_coin_b ON coin.tax_rate (coin_b)
    """))

    # Añadir columnas solo si no existen (por si 015 se ejecutó parcialmente antes)
    conn = op.get_bind()
    r = conn.execute(sa.text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'transaction' AND table_name = 'transactions' AND column_name = 'bank_account_id'
    """))
    if r.fetchone() is None:
        op.add_column(
            "transactions",
            sa.Column("bank_account_id", sa.UUID(), nullable=True),
            schema=schema,
        )
        op.add_column(
            "transactions",
            sa.Column("user_id", sa.UUID(), nullable=True),
            schema=schema,
        )
        op.add_column(
            "transactions",
            sa.Column("tax_rate_id", sa.UUID(), nullable=True),
            schema=schema,
        )
        op.add_column(
            "transactions",
            sa.Column("commission_id", sa.UUID(), nullable=True),
            schema=schema,
        )
        op.add_column(
            "transactions",
            sa.Column("origin_amount", sa.Numeric(20, 8), nullable=True),
            schema=schema,
        )
        op.add_column(
            "transactions",
            sa.Column("destination_amount", sa.Numeric(20, 8), nullable=True),
            schema=schema,
        )
        op.add_column(
            "transactions",
            sa.Column("code", sa.String(80), nullable=True),
            schema=schema,
        )
        op.add_column(
            "transactions",
            sa.Column("send_date", sa.DateTime(timezone=True), nullable=True),
            schema=schema,
        )
        op.add_column(
            "transactions",
            sa.Column("payment_date", sa.DateTime(timezone=True), nullable=True),
            schema=schema,
        )
        op.add_column(
            "transactions",
            sa.Column("send_voucher", sa.String(500), nullable=True),
            schema=schema,
        )
        op.add_column(
            "transactions",
            sa.Column("payment_voucher", sa.String(500), nullable=True),
            schema=schema,
        )

    # FKs e índices solo si no existen (por si 015 se ejecutó parcialmente)
    def constraint_exists(name: str) -> bool:
        r = conn.execute(sa.text("""
            SELECT 1 FROM information_schema.table_constraints
            WHERE table_schema = :schema AND table_name = 'transactions' AND constraint_name = :name
        """), {"schema": schema, "name": name})
        return r.fetchone() is not None

    def index_exists(index_name: str) -> bool:
        r = conn.execute(sa.text("""
            SELECT 1 FROM pg_indexes
            WHERE schemaname = :schema AND tablename = 'transactions' AND indexname = :name
        """), {"schema": schema, "name": index_name})
        return r.fetchone() is not None

    if not constraint_exists("fk_transactions_bank_account_id_bank_accounts"):
        op.create_foreign_key(
            "fk_transactions_bank_account_id_bank_accounts",
            "transactions",
            "bank_accounts",
            ["bank_account_id"],
            ["id"],
            source_schema=schema,
            referent_schema=schema,
        )
    if not constraint_exists("fk_transactions_user_id_user"):
        op.create_foreign_key(
            "fk_transactions_user_id_user",
            "transactions",
            "user",
            ["user_id"],
            ["id"],
            source_schema=schema,
            referent_schema="user",
        )
    if not constraint_exists("fk_transactions_tax_rate_id_tax_rate"):
        op.create_foreign_key(
            "fk_transactions_tax_rate_id_tax_rate",
            "transactions",
            "tax_rate",
            ["tax_rate_id"],
            ["id"],
            source_schema=schema,
            referent_schema="coin",
        )
    if not constraint_exists("fk_transactions_commission_id_commission"):
        op.create_foreign_key(
            "fk_transactions_commission_id_commission",
            "transactions",
            "commission",
            ["commission_id"],
            ["id"],
            source_schema=schema,
            referent_schema="coin",
        )

    if not index_exists("ix_transaction_transactions_bank_account_id"):
        op.create_index(
            op.f("ix_transaction_transactions_bank_account_id"),
            "transactions",
            ["bank_account_id"],
            schema=schema,
        )
    if not index_exists("ix_transaction_transactions_user_id"):
        op.create_index(
            op.f("ix_transaction_transactions_user_id"),
            "transactions",
            ["user_id"],
            schema=schema,
        )
    if not index_exists("ix_transaction_transactions_tax_rate_id"):
        op.create_index(
            op.f("ix_transaction_transactions_tax_rate_id"),
            "transactions",
            ["tax_rate_id"],
            schema=schema,
        )
    if not index_exists("ix_transaction_transactions_commission_id"):
        op.create_index(
            op.f("ix_transaction_transactions_commission_id"),
            "transactions",
            ["commission_id"],
            schema=schema,
        )
    if not index_exists("ix_transaction_transactions_code"):
        op.create_index(
            op.f("ix_transaction_transactions_code"),
            "transactions",
            ["code"],
            schema=schema,
        )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_transaction_transactions_code"),
        table_name="transactions",
        schema=schema,
    )
    op.drop_index(
        op.f("ix_transaction_transactions_commission_id"),
        table_name="transactions",
        schema=schema,
    )
    op.drop_index(
        op.f("ix_transaction_transactions_tax_rate_id"),
        table_name="transactions",
        schema=schema,
    )
    op.drop_index(
        op.f("ix_transaction_transactions_user_id"),
        table_name="transactions",
        schema=schema,
    )
    op.drop_index(
        op.f("ix_transaction_transactions_bank_account_id"),
        table_name="transactions",
        schema=schema,
    )
    op.drop_constraint(
        "fk_transactions_commission_id_commission",
        "transactions",
        schema=schema,
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_transactions_tax_rate_id_tax_rate",
        "transactions",
        schema=schema,
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_transactions_user_id_user",
        "transactions",
        schema=schema,
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_transactions_bank_account_id_bank_accounts",
        "transactions",
        schema=schema,
        type_="foreignkey",
    )
    op.drop_column("transactions", "payment_voucher", schema=schema)
    op.drop_column("transactions", "send_voucher", schema=schema)
    op.drop_column("transactions", "payment_date", schema=schema)
    op.drop_column("transactions", "send_date", schema=schema)
    op.drop_column("transactions", "code", schema=schema)
    op.drop_column("transactions", "destination_amount", schema=schema)
    op.drop_column("transactions", "origin_amount", schema=schema)
    op.drop_column("transactions", "commission_id", schema=schema)
    op.drop_column("transactions", "tax_rate_id", schema=schema)
    op.drop_column("transactions", "user_id", schema=schema)
    op.drop_column("transactions", "bank_account_id", schema=schema)
