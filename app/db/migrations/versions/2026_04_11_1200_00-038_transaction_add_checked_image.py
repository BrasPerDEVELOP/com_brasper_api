"""transaction_add_checked_image

Revision ID: 038
Revises: 037
Create Date: 2026-04-11

Añade columna checked_image (ruta de imagen del checklist) a transaction.transactions.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "038"
down_revision: Union[str, None] = "037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "transaction"


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("checked_image", sa.String(length=500), nullable=True),
        schema=schema,
    )


def downgrade() -> None:
    op.drop_column("transactions", "checked_image", schema=schema)
