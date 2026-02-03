"""commission_reverse_to_numeric

Revision ID: 019
Revises: 018
Create Date: 2025-02-02

Cambia coin.commission.reverse de BOOLEAN a NUMERIC(20, 8) con default 0.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "coin"
table = "commission"
column = "reverse"


def upgrade() -> None:
    # Quitar default booleano para poder cambiar el tipo
    op.execute(sa.text(f"""
        ALTER TABLE {schema}.{table}
        ALTER COLUMN {column} DROP DEFAULT
    """))
    # Convertir BOOLEAN a NUMERIC: true -> 1, false -> 0
    op.execute(sa.text(f"""
        ALTER TABLE {schema}.{table}
        ALTER COLUMN {column} TYPE NUMERIC(20, 8)
        USING (CASE WHEN {column} THEN 1 ELSE 0 END)
    """))
    op.execute(sa.text(f"""
        ALTER TABLE {schema}.{table}
        ALTER COLUMN {column} SET DEFAULT 0
    """))


def downgrade() -> None:
    # Quitar default numérico para poder cambiar el tipo
    op.execute(sa.text(f"""
        ALTER TABLE {schema}.{table}
        ALTER COLUMN {column} DROP DEFAULT
    """))
    # Volver a BOOLEAN: distinto de 0 -> true, 0 -> false
    op.execute(sa.text(f"""
        ALTER TABLE {schema}.{table}
        ALTER COLUMN {column} TYPE BOOLEAN
        USING ({column} != 0)
    """))
    op.execute(sa.text(f"""
        ALTER TABLE {schema}.{table}
        ALTER COLUMN {column} SET DEFAULT false
    """))
