"""transactions_created_at_index

Revision ID: 055
Revises: 054
Create Date: 2026-07-02 12:00:00.000000

Índice en transaction.transactions.created_at: es la columna de orden por defecto
de todos los listados (ORDER BY created_at DESC). Sin él, cada listado hace un
seq scan + sort de toda la tabla, lo que se degrada al crecer el volumen.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "055"
down_revision: Union[str, None] = "054"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_transaction_transactions_created_at",
        "transactions",
        ["created_at"],
        unique=False,
        schema="transaction",
        postgresql_ops={"created_at": "DESC"},
    )


def downgrade() -> None:
    op.drop_index(
        "ix_transaction_transactions_created_at",
        table_name="transactions",
        schema="transaction",
    )
