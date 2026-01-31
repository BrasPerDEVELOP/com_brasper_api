"""add_user_role_and_document_type

Revision ID: 003
Revises: 002
Create Date: 2025-01-29

Añade columnas role y document_type (enum como string) a user.user.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "user"


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("role", sa.String(20), nullable=True),
        schema=schema,
    )
    op.add_column(
        "user",
        sa.Column("document_type", sa.String(20), nullable=True),
        schema=schema,
    )


def downgrade() -> None:
    op.drop_column("user", "document_type", schema=schema)
    op.drop_column("user", "role", schema=schema)
