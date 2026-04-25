"""brasper contact_form schema and table

Revision ID: 042
Revises: 041
Create Date: 2026-04-25

Crea esquema brasper y tabla contac_form (formulario de contacto / membresía).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "042"
down_revision: Union[str, None] = "041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "brasper"
table = "contac_form"


def upgrade() -> None:
    op.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    op.execute(
        sa.text(
            f"""
        CREATE TABLE {schema}.{table} (
            id UUID NOT NULL PRIMARY KEY,
            deleted BOOLEAN NOT NULL DEFAULT false,
            enable BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            created_by VARCHAR(250),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            full_name VARCHAR(200) NOT NULL,
            email VARCHAR(255) NOT NULL,
            affiliation VARCHAR(500) NOT NULL,
            profile VARCHAR(200) NOT NULL,
            interest VARCHAR(500) NOT NULL,
            message TEXT NOT NULL,
            locale VARCHAR(10) NOT NULL,
            source VARCHAR(100) NOT NULL,
            submitted_at TIMESTAMP WITH TIME ZONE NOT NULL
        )
    """
        )
    )
    op.execute(
        sa.text(
            f'CREATE INDEX ix_{table}_email ON {schema}.{table} (email)'
        )
    )


def downgrade() -> None:
    op.drop_index(f"ix_{table}_email", table_name=table, schema=schema)
    op.drop_table(table, schema=schema)
    op.execute(sa.text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
