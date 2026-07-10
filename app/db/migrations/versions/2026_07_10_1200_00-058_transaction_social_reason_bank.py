"""transaction_social_reason_bank

Revision ID: 058
Revises: 057
Create Date: 2026-07-10 12:00:00.000000

Persiste el banco exacto elegido como razón social, separado del banco de la
cuenta destino. Las transacciones existentes quedan en NULL porque el nombre
histórico no permite distinguir bancos con la misma empresa.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "058"
down_revision: Union[str, None] = "057"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "transaction"
table = "transactions"
column = "social_reason_bank_id"
constraint = "fk_transactions_social_reason_bank_id_banks"
index = "ix_transaction_transactions_social_reason_bank_id"


def upgrade() -> None:
    op.add_column(
        table,
        sa.Column(column, sa.UUID(), nullable=True),
        schema=schema,
    )
    op.create_foreign_key(
        constraint,
        table,
        "banks",
        [column],
        ["id"],
        source_schema=schema,
        referent_schema=schema,
    )
    op.create_index(
        op.f(index),
        table,
        [column],
        schema=schema,
    )


def downgrade() -> None:
    op.drop_index(op.f(index), table_name=table, schema=schema)
    op.drop_constraint(constraint, table, schema=schema, type_="foreignkey")
    op.drop_column(table, column, schema=schema)
