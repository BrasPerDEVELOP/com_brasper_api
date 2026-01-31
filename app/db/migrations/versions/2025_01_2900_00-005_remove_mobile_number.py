"""remove_mobile_number

Revision ID: 005
Revises: 004
Create Date: 2025-01-29

Elimina la columna mobile_number de user.user.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "user"
table = "user"
index_name = "ix_user_user_mobile_number"


def upgrade() -> None:
    op.drop_index(index_name, table_name=table, schema=schema, if_exists=True)
    op.drop_column(table, "mobile_number", schema=schema)


def downgrade() -> None:
    op.add_column(
        table,
        sa.Column("mobile_number", sa.String(20), nullable=True),
        schema=schema,
    )
    op.create_index(
        op.f(index_name),
        table,
        ["mobile_number"],
        unique=True,
        schema=schema,
    )
