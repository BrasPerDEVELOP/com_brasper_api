"""create_integrations_schema_and_integration_table

Revision ID: 020
Revises: 019
Create Date: 2025-02-03

Crea esquema integrations, tipo enum integration_type (webhook, api, oauth)
y tabla integration (name, provider, integration_type, config JSONB, description).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "integrations"


def upgrade() -> None:
    op.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    op.execute(sa.text(
        "DO $$ BEGIN "
        "CREATE TYPE integrations.integration_type AS ENUM ('webhook', 'api', 'oauth'); "
        "EXCEPTION WHEN duplicate_object THEN null; "
        "END $$"
    ))
    op.execute(sa.text("""
        CREATE TABLE integrations.integration (
            id UUID NOT NULL PRIMARY KEY,
            deleted BOOLEAN NOT NULL DEFAULT false,
            enable BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            created_by VARCHAR(250),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            name VARCHAR(250) NOT NULL,
            provider VARCHAR(100) NOT NULL,
            integration_type integrations.integration_type NOT NULL,
            config JSONB,
            description TEXT
        )
    """))
    op.create_index(
        op.f("ix_integrations_integration_name"), "integration", ["name"], schema=schema
    )
    op.create_index(
        op.f("ix_integrations_integration_provider"), "integration", ["provider"], schema=schema
    )
    op.create_index(
        op.f("ix_integrations_integration_integration_type"),
        "integration",
        ["integration_type"],
        schema=schema,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_integrations_integration_integration_type"),
        table_name="integration",
        schema=schema,
    )
    op.drop_index(
        op.f("ix_integrations_integration_provider"), table_name="integration", schema=schema
    )
    op.drop_index(
        op.f("ix_integrations_integration_name"), table_name="integration", schema=schema
    )
    op.drop_table("integration", schema=schema)
    op.execute(sa.text("DROP TYPE IF EXISTS integrations.integration_type CASCADE"))
    op.execute(sa.text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
