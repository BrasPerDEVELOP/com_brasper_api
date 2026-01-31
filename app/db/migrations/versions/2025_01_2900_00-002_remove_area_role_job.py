"""remove_area_role_job

Revision ID: 002
Revises: 001
Create Date: 2025-01-29

Elimina tablas y columnas de area, role y job.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "user"


def upgrade() -> None:
    conn = op.get_bind()

    def table_exists(table_name: str) -> bool:
        result = conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = :schema AND table_name = :name"
            ),
            {"schema": schema, "name": table_name},
        )
        return result.scalar() is not None

    def column_exists(table_name: str, column_name: str) -> bool:
        result = conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = :schema AND table_name = :name AND column_name = :col"
            ),
            {"schema": schema, "name": table_name, "col": column_name},
        )
        return result.scalar() is not None

    # 1. Eliminar tabla user_area (relación usuario-área)
    if table_exists("user_area"):
        op.drop_table("user_area", schema=schema)

    # 2. Eliminar columnas role_id y job_id de user (primero las FK)
    if table_exists("user"):
        for col in ("role_id", "job_id"):
            if not column_exists("user", col):
                continue
            # Obtener nombre real de la FK para esta columna
            r = conn.execute(
                sa.text(
                    "SELECT c.conname FROM pg_constraint c "
                    "JOIN pg_namespace n ON n.oid = c.connamespace "
                    "JOIN pg_class t ON t.oid = c.conrelid "
                    "JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey) AND a.attname = :col "
                    "WHERE n.nspname = :schema AND t.relname = 'user' AND c.contype = 'f' AND NOT a.attisdropped"
                ),
                {"schema": schema, "col": col},
            )
            row = r.fetchone()
            if row:
                op.drop_constraint(row[0], "user", schema=schema, type_="foreignkey")
            op.drop_column("user", col, schema=schema)

    # 3. Eliminar tablas job, area, role
    if table_exists("job"):
        op.drop_table("job", schema=schema)
    if table_exists("area"):
        op.drop_table("area", schema=schema)
    if table_exists("role"):
        op.drop_table("role", schema=schema)


def downgrade() -> None:
    # Recrear tablas y columnas (estructura mínima para poder volver atrás)
    from sqlalchemy.dialects import postgresql

    op.create_table(
        "role",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("enable", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(250), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("permissions", postgresql.ARRAY(sa.String()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema=schema,
    )

    op.create_table(
        "area",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("enable", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(250), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("color", sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema=schema,
    )

    op.create_table(
        "job",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("enable", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(250), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema=schema,
    )

    op.add_column("user", sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=True), schema=schema)
    op.add_column("user", sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True), schema=schema)
    op.create_foreign_key(
        "user_role_id_fkey", "user", "role",
        ["role_id"], ["id"], source_schema=schema, referent_schema=schema,
    )
    op.create_foreign_key(
        "user_job_id_fkey", "user", "job",
        ["job_id"], ["id"], source_schema=schema, referent_schema=schema,
    )

    op.create_table(
        "user_area",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("enable", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(250), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("area_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["area_id"], [f"{schema}.area.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], [f"{schema}.user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "area_id", name="unique_user_area"),
        schema=schema,
    )
