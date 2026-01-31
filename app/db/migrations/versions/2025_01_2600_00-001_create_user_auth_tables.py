"""create_user_auth_tables

Revision ID: 001
Revises:
Create Date: 2025-01-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Esquema donde se crean las tablas
schema = "user"


def _ref(table: str) -> str:
    """Referencia a columna para FK. Sin comillas para que SQLAlchemy cite cada parte una vez."""
    return f"{schema}.{table}.id"


def _table_exists(conn, table_name: str) -> bool:
    """True si la tabla existe en el esquema."""
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :name"
        ),
        {"schema": schema, "name": table_name},
    )
    return result.scalar() is not None


def upgrade() -> None:
    conn = op.get_bind()

    # Crear esquema "user" si no existe
    op.execute(sa.text("CREATE SCHEMA IF NOT EXISTS \"{}\"".format(schema)))

    # Tabla auth_login (credenciales de autenticación)
    if not _table_exists(conn, "auth_login"):
        op.create_table(
            "auth_login",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("enable", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("created_by", sa.String(250), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("username", sa.String(255), nullable=False),
            sa.Column("password", sa.String(255), nullable=False),
            sa.Column("recovery_code", sa.String(50), nullable=True),
            sa.Column("token", sa.String(1000), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            schema=schema,
        )
        op.create_index(op.f("ix_user_auth_login_username"), "auth_login", ["username"], unique=True, schema=schema)

    # Tabla role
    if not _table_exists(conn, "role"):
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

    # Tabla area
    if not _table_exists(conn, "area"):
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

    # Tabla job
    if not _table_exists(conn, "job"):
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

    # Tabla user (usuarios)
    if not _table_exists(conn, "user"):
        op.create_table(
            "user",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("enable", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("created_by", sa.String(250), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("auth_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("names", sa.String(100), nullable=False),
            sa.Column("lastnames", sa.String(100), nullable=False),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("profile_image", sa.String(255), nullable=True),
            sa.Column("document_number", sa.String(20), nullable=True),
            sa.Column("mobile_number", sa.String(20), nullable=True),
            sa.Column("commercial_color", sa.String(250), nullable=True),
            sa.Column("is_agent", sa.Boolean(), nullable=True, server_default=sa.text("true")),
            sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.ForeignKeyConstraint(["job_id"], [_ref("job")]),
            sa.ForeignKeyConstraint(["role_id"], [_ref("role")]),
            sa.PrimaryKeyConstraint("id"),
            schema=schema,
        )
        op.create_index(op.f("ix_user_user_email"), "user", ["email"], unique=True, schema=schema)
        op.create_index(op.f("ix_user_user_document_number"), "user", ["document_number"], unique=True, schema=schema)
        op.create_index(op.f("ix_user_user_mobile_number"), "user", ["mobile_number"], unique=True, schema=schema)

    # Tabla user_area (relación muchos a muchos usuario - área)
    if not _table_exists(conn, "user_area"):
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
            sa.ForeignKeyConstraint(["area_id"], [_ref("area")], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], [_ref("user")], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "area_id", name="unique_user_area"),
            schema=schema,
        )


def downgrade() -> None:
    op.drop_table("user_area", schema=schema)
    op.drop_table("user", schema=schema)
    op.drop_table("job", schema=schema)
    op.drop_table("area", schema=schema)
    op.drop_table("role", schema=schema)
    op.drop_index(op.f("ix_user_auth_login_username"), table_name="auth_login", schema=schema)
    op.drop_table("auth_login", schema=schema)
    op.execute(sa.text("DROP SCHEMA IF EXISTS \"{}\"".format(schema)))
