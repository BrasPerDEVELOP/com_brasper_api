"""transaction_tags

Revision ID: 062
Revises: 061
Create Date: 2026-08-09 12:00:00.000000

Catálogo de etiquetas de transacción y su tabla puente.

Ventas necesita marcar los envíos (sobre todo «Cliente nuevo») y contar cuántos
clientes nuevos entran y cuántos finalizan cada día. `counts_as_new_client`
señala la única etiqueta que alimenta ese indicador; la exclusividad la aplica
el caso de uso, porque el borrado es lógico y un índice único parcial estorbaría
al reactivar una etiqueta borrada.

Se siembran las cinco etiquetas que ventas validó en el mockup, para que la
pantalla no arranque vacía.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "062"
down_revision: Union[str, None] = "061"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "transaction"
tags_table = "tags"
bridge_table = "transaction_tags"


def upgrade() -> None:
    op.create_table(
        tags_table,
        sa.Column("label", sa.String(length=60), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=False, server_default="slate"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "counts_as_new_client",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", sa.String(length=250), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tags"),
        schema=schema,
    )
    op.create_index(
        op.f("ix_transaction_tags_label"), tags_table, ["label"], schema=schema
    )
    op.create_index(
        op.f("ix_transaction_tags_counts_as_new_client"),
        tags_table,
        ["counts_as_new_client"],
        schema=schema,
    )

    op.create_table(
        bridge_table,
        sa.Column("transaction_id", sa.UUID(), nullable=False),
        sa.Column("tag_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", sa.String(length=250), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transaction.transactions.id"],
            name="fk_transaction_tags_transaction_id_transactions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["transaction.tags.id"],
            name="fk_transaction_tags_tag_id_tags",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_transaction_tags"),
        sa.UniqueConstraint("transaction_id", "tag_id", name="uq_transaction_tag"),
        schema=schema,
    )
    op.create_index(
        op.f("ix_transaction_transaction_tags_transaction_id"),
        bridge_table,
        ["transaction_id"],
        schema=schema,
    )
    op.create_index(
        op.f("ix_transaction_transaction_tags_tag_id"),
        bridge_table,
        ["tag_id"],
        schema=schema,
    )

    # Semilla del catálogo validado en el mockup. gen_random_uuid() viene de
    # pgcrypto, disponible en PostgreSQL 13+ sin extensión adicional.
    op.execute(
        sa.text(
            """
            INSERT INTO transaction.tags
                (id, label, color, active, counts_as_new_client, position,
                 deleted, enable, created_at, updated_at)
            VALUES
                (gen_random_uuid(), 'Cliente nuevo', 'amber',  true, true,  0, false, true, now(), now()),
                (gen_random_uuid(), 'Recurrente',    'blue',   true, false, 1, false, true, now(), now()),
                (gen_random_uuid(), 'Campaña',       'purple', true, false, 2, false, true, now(), now()),
                (gen_random_uuid(), 'Seguimiento',   'rose',   true, false, 3, false, true, now(), now()),
                (gen_random_uuid(), 'VIP',           'green',  true, false, 4, false, true, now(), now())
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_transaction_transaction_tags_tag_id"),
        table_name=bridge_table,
        schema=schema,
    )
    op.drop_index(
        op.f("ix_transaction_transaction_tags_transaction_id"),
        table_name=bridge_table,
        schema=schema,
    )
    op.drop_table(bridge_table, schema=schema)

    op.drop_index(
        op.f("ix_transaction_tags_counts_as_new_client"),
        table_name=tags_table,
        schema=schema,
    )
    op.drop_index(op.f("ix_transaction_tags_label"), table_name=tags_table, schema=schema)
    op.drop_table(tags_table, schema=schema)
