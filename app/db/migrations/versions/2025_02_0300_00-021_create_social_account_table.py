"""create_social_account_table

Revision ID: 021
Revises: 020
Create Date: 2025-02-03

Crea tabla social_account en esquema integrations para vincular usuarios
con cuentas OAuth (Google, Facebook): user_id, provider, provider_user_id, email, tokens.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "integrations"


def upgrade() -> None:
    op.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    op.execute(sa.text("""
        CREATE TABLE integrations.social_account (
            id UUID NOT NULL PRIMARY KEY,
            deleted BOOLEAN NOT NULL DEFAULT false,
            enable BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            created_by VARCHAR(250),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            user_id UUID NOT NULL REFERENCES "user".user(id) ON DELETE CASCADE,
            provider VARCHAR(50) NOT NULL,
            provider_user_id VARCHAR(255) NOT NULL,
            email VARCHAR(255),
            access_token TEXT,
            refresh_token TEXT
        )
    """))
    op.create_index(
        op.f("ix_integrations_social_account_user_id"),
        "social_account",
        ["user_id"],
        schema=schema,
    )
    op.create_index(
        op.f("ix_integrations_social_account_provider"),
        "social_account",
        ["provider"],
        schema=schema,
    )
    op.create_index(
        op.f("ix_integrations_social_account_provider_user_id"),
        "social_account",
        ["provider_user_id"],
        schema=schema,
    )
    op.create_index(
        "ix_integrations_social_account_provider_provider_user_id",
        "social_account",
        ["provider", "provider_user_id"],
        schema=schema,
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_integrations_social_account_provider_provider_user_id",
        table_name="social_account",
        schema=schema,
    )
    op.drop_index(
        op.f("ix_integrations_social_account_provider_user_id"),
        table_name="social_account",
        schema=schema,
    )
    op.drop_index(
        op.f("ix_integrations_social_account_provider"),
        table_name="social_account",
        schema=schema,
    )
    op.drop_index(
        op.f("ix_integrations_social_account_user_id"),
        table_name="social_account",
        schema=schema,
    )
    op.drop_table("social_account", schema=schema)
