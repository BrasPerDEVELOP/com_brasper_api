"""add_phone_code_phone_and_optional_user_fields

Revision ID: 004
Revises: 003
Create Date: 2025-01-29

Añade columnas phone (BigInteger, 15 dígitos) y code_phone (código país).
Hace opcionales names, lastnames y email en user.user.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "user"


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("phone", sa.BigInteger(), nullable=True),
        schema=schema,
    )
    op.add_column(
        "user",
        sa.Column("code_phone", sa.String(10), nullable=True),
        schema=schema,
    )
    op.alter_column(
        "user",
        "names",
        existing_type=sa.String(100),
        nullable=True,
        schema=schema,
    )
    op.alter_column(
        "user",
        "lastnames",
        existing_type=sa.String(100),
        nullable=True,
        schema=schema,
    )
    op.alter_column(
        "user",
        "email",
        existing_type=sa.String(255),
        nullable=True,
        schema=schema,
    )


def downgrade() -> None:
    op.alter_column(
        "user",
        "email",
        existing_type=sa.String(255),
        nullable=False,
        schema=schema,
    )
    op.alter_column(
        "user",
        "lastnames",
        existing_type=sa.String(100),
        nullable=False,
        schema=schema,
    )
    op.alter_column(
        "user",
        "names",
        existing_type=sa.String(100),
        nullable=False,
        schema=schema,
    )
    op.drop_column("user", "code_phone", schema=schema)
    op.drop_column("user", "phone", schema=schema)
