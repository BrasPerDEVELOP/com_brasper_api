"""repair_home_banner_schema

Revision ID: 041
Revises: 040
Create Date: 2026-04-17

Repara el drift de esquema creando home_banner.home_banner si falta
en bases donde Alembic ya quedó en head pero la tabla no existe.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "041"
down_revision: Union[str, None] = "040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "home_banner"
table = "home_banner"


def _column_exists(conn, column_name: str) -> bool:
    result = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name = :table
              AND column_name = :column_name
            """
        ),
        {"schema": schema, "table": table, "column_name": column_name},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    conn = op.get_bind()

    op.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    op.execute(
        sa.text(
            f"""
            CREATE TABLE IF NOT EXISTS {schema}.{table} (
                id UUID NOT NULL PRIMARY KEY,
                deleted BOOLEAN NOT NULL DEFAULT false,
                enable BOOLEAN NOT NULL DEFAULT true,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                created_by VARCHAR(250),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                banner_es VARCHAR(500),
                banner_pr VARCHAR(500),
                banner_en VARCHAR(500)
            )
            """
        )
    )

    missing_columns = [
        ("deleted", "BOOLEAN NOT NULL DEFAULT false"),
        ("enable", "BOOLEAN NOT NULL DEFAULT true"),
        ("created_at", "TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()"),
        ("created_by", "VARCHAR(250)"),
        ("updated_at", "TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()"),
        ("banner_es", "VARCHAR(500)"),
        ("banner_pr", "VARCHAR(500)"),
        ("banner_en", "VARCHAR(500)"),
    ]

    for column_name, column_definition in missing_columns:
        if not _column_exists(conn, column_name):
            op.execute(
                sa.text(
                    f"""
                    ALTER TABLE {schema}.{table}
                    ADD COLUMN {column_name} {column_definition}
                    """
                )
            )


def downgrade() -> None:
    op.drop_table(table, schema=schema)
    op.execute(sa.text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
