"""transaction_bank_id_and_names

Revision ID: 047
Revises: 046
Create Date: 2026-05-12

FK a transaction.banks y snapshot bank_name / company_name en transaction.transactions.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "047"
down_revision: Union[str, None] = "046"
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


def _fk_exists(conn, constraint_name: str) -> bool:
    row = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.table_constraints
            WHERE table_schema = :schema
              AND table_name = :table
              AND constraint_name = :name
            """
        ),
        {"schema": schema, "table": table, "name": constraint_name},
    ).fetchone()
    return row is not None


def _index_exists(conn, index_name: str) -> bool:
    row = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = :schema
              AND tablename = :table
              AND indexname = :indexname
            """
        ),
        {"schema": schema, "table": table, "indexname": index_name},
    ).fetchone()
    return row is not None


def upgrade() -> None:
    conn = op.get_bind()

    if not _column_exists(conn, "bank_id"):
        op.add_column(
            table,
            sa.Column("bank_id", sa.UUID(), nullable=True),
            schema=schema,
        )

    if not _fk_exists(conn, "fk_transactions_bank_id_banks"):
        op.create_foreign_key(
            "fk_transactions_bank_id_banks",
            table,
            "banks",
            ["bank_id"],
            ["id"],
            source_schema=schema,
            referent_schema=schema,
        )

    idx = "ix_transaction_transactions_bank_id"
    if not _index_exists(conn, idx):
        op.create_index(
            op.f(idx),
            table,
            ["bank_id"],
            schema=schema,
        )

    if not _column_exists(conn, "bank_name"):
        op.add_column(
            table,
            sa.Column("bank_name", sa.String(length=120), nullable=True),
            schema=schema,
        )

    if not _column_exists(conn, "company_name"):
        op.add_column(
            table,
            sa.Column("company_name", sa.String(length=200), nullable=True),
            schema=schema,
        )


def downgrade() -> None:
    conn = op.get_bind()

    if _column_exists(conn, "company_name"):
        op.drop_column(table, "company_name", schema=schema)

    if _column_exists(conn, "bank_name"):
        op.drop_column(table, "bank_name", schema=schema)

    idx = "ix_transaction_transactions_bank_id"
    if _index_exists(conn, idx):
        op.drop_index(
            op.f(idx),
            table_name=table,
            schema=schema,
        )

    if _fk_exists(conn, "fk_transactions_bank_id_banks"):
        op.drop_constraint(
            "fk_transactions_bank_id_banks",
            table,
            schema=schema,
            type_="foreignkey",
        )

    if _column_exists(conn, "bank_id"):
        op.drop_column(table, "bank_id", schema=schema)
