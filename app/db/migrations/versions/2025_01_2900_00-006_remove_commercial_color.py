"""remove_commercial_color

Revision ID: 006
Revises: 005
Create Date: 2025-01-29

Elimina la columna commercial_color de user.user.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "user"


def upgrade() -> None:
    op.drop_column("user", "commercial_color", schema=schema)


def downgrade() -> None:
    op.add_column(
        "user",
        sa.Column("commercial_color", sa.String(250), nullable=True),
        schema=schema,
    )
