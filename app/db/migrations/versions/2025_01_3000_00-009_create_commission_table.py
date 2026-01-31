"""create_commission_table

Revision ID: 009
Revises: 008
Create Date: 2025-01-30

Crea tabla commission en esquema coin (coin_a, coin_b, percentage, reverse).
Usa tipo enum currency (pen, brl, usd).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "coin"


def upgrade() -> None:
    op.execute(sa.text(f'CREATE schema IF NOT EXISTS "{schema}"'))
    # Crear tipo enum solo si no existe (por si tax_rate ya lo creó)
    op.execute(sa.text(
        "DO $$ BEGIN CREATE TYPE coin.currency AS ENUM ('pen', 'brl', 'usd'); EXCEPTION WHEN duplicate_object THEN null; END $$"
    ))
    # Crear tabla con SQL directo para referenciar coin.currency sin que SQLAlchemy emita CREATE TYPE
    op.execute(sa.text("""
        CREATE TABLE coin.commission (
            id UUID NOT NULL PRIMARY KEY,
            deleted BOOLEAN NOT NULL DEFAULT false,
            enable BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            created_by VARCHAR(250),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            coin_a coin.currency NOT NULL,
            coin_b coin.currency NOT NULL,
            percentage NUMERIC(20, 8) NOT NULL DEFAULT 0,
            reverse BOOLEAN NOT NULL DEFAULT false
        )
    """))
    op.create_index(op.f("ix_coin_commission_coin_a"), "commission", ["coin_a"], schema=schema)
    op.create_index(op.f("ix_coin_commission_coin_b"), "commission", ["coin_b"], schema=schema)


def downgrade() -> None:
    op.drop_index(op.f("ix_coin_commission_coin_b"), table_name="commission", schema=schema)
    op.drop_index(op.f("ix_coin_commission_coin_a"), table_name="commission", schema=schema)
    op.drop_table("commission", schema=schema)
    # No eliminamos el tipo currency por si tax_rate lo usa
    op.execute(sa.text('DROP TYPE IF EXISTS coin.currency CASCADE'))
