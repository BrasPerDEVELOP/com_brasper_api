"""ensure_coin_schema_and_currency_enum

Revision ID: 018
Revises: 017
Create Date: 2025-02-02

Asegura que existan el esquema coin y el tipo coin.currency (ENUM).
Idempotente: no falla si ya existen.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text('CREATE SCHEMA IF NOT EXISTS coin'))
    op.execute(sa.text(
        "DO $$ BEGIN "
        "CREATE TYPE coin.currency AS ENUM ('pen', 'brl', 'usd'); "
        "EXCEPTION WHEN duplicate_object THEN null; "
        "END $$"
    ))


def downgrade() -> None:
    # No eliminamos coin.currency ni el esquema: otras tablas (tax_rate, commission, etc.) los usan.
    pass
