"""user_multiple_identifications

Revision ID: 060
Revises: 059
Create Date: 2026-07-21 12:00:00.000000

Normaliza los documentos del usuario en una relación uno-a-muchos y migra
el documento legacy existente como identificación principal.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "060"
down_revision: Union[str, None] = "059"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "user"
table = "user_identifications"


def upgrade() -> None:
    op.create_table(
        table,
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("document_type", sa.String(length=20), nullable=False),
        sa.Column("document_number", sa.String(length=40), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.String(length=250), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.user.id"],
            name="fk_user_identifications_user_id_user",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_user_identifications"),
        sa.UniqueConstraint(
            "document_type",
            "document_number",
            name="uq_user_identifications_type_number",
        ),
        schema=schema,
    )
    op.create_index(
        op.f("ix_user_user_identifications_user_id"),
        table,
        ["user_id"],
        schema=schema,
    )
    op.execute(sa.text(
        '''
        INSERT INTO "user".user_identifications
            (id, user_id, document_type, document_number, is_primary, position,
             deleted, enable, created_at, updated_at)
        SELECT id, id, document_type, document_number, true, 0,
               false, true, created_at, updated_at
        FROM "user"."user"
        WHERE deleted = false
          AND document_type IS NOT NULL
          AND document_number IS NOT NULL
        '''
    ))


def downgrade() -> None:
    op.drop_index(
        op.f("ix_user_user_identifications_user_id"),
        table_name=table,
        schema=schema,
    )
    op.drop_table(table, schema=schema)
