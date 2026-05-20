"""create_blog_table

Revision ID: e990d42abded
Revises: 048
Create Date: 2026-05-20 13:03:42.050710

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e990d42abded'
down_revision: Union[str, None] = '048'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "blog"
table = "blog"


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
            title VARCHAR(255) NOT NULL,
            slug VARCHAR(255) NOT NULL,
            excerpt TEXT,
            content TEXT NOT NULL,
            category VARCHAR(100),
            public_id VARCHAR(100),
            read_time INTEGER,
            date TIMESTAMP WITH TIME ZONE,
            language VARCHAR(10) NOT NULL
        )
        """
        )
    )
    op.execute(sa.text(f'CREATE UNIQUE INDEX ix_{table}_slug ON {schema}.{table} (slug)'))
    op.execute(sa.text(f'CREATE UNIQUE INDEX ix_{table}_public_id ON {schema}.{table} (public_id)'))


def downgrade() -> None:
    op.drop_index(f"ix_{table}_public_id", table_name=table, schema=schema)
    op.drop_index(f"ix_{table}_slug", table_name=table, schema=schema)
    op.drop_table(table, schema=schema)
    op.execute(sa.text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
