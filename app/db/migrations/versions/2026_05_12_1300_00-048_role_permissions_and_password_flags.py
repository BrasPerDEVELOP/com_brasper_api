"""role_permissions_and_password_flags

Revision ID: 048
Revises: 047
Create Date: 2026-05-12

Agrega permisos configurables por rol y flag de cambio obligatorio de contraseña.
"""

from typing import Sequence, Union
import json
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "048"
down_revision: Union[str, None] = "047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "user"

role_permissions = {
    "admin": [
        "dashboard.view",
        "users.view",
        "users.create",
        "users.update",
        "users.delete",
        "users.reset_password",
        "roles.permissions.view",
        "roles.permissions.update",
        "transactions.view",
        "transactions.create",
        "transactions.update",
        "transactions.delete",
        "accounting.view",
        "calculator.view",
        "coupons.view",
        "coupons.create",
        "coupons.update",
        "coupons.delete",
        "bank_accounts.view",
        "bank_accounts.create",
        "bank_accounts.update",
        "bank_accounts.delete",
        "commissions.view",
        "commissions.create",
        "commissions.update",
        "commissions.delete",
        "rates.view",
        "rates.create",
        "rates.update",
        "rates.delete",
        "home_banner.view",
        "home_banner.update",
        "profile.view",
        "profile.update",
        "profile.change_password",
    ],
    "client": [
        "dashboard.view",
        "calculator.view",
        "profile.view",
        "profile.update",
        "profile.change_password",
    ],
    "sales": [
        "dashboard.view",
        "users.view",
        "users.create",
        "users.update",
        "transactions.view",
        "transactions.create",
        "transactions.update",
        "calculator.view",
        "coupons.view",
        "coupons.create",
        "coupons.update",
        "profile.view",
        "profile.update",
        "profile.change_password",
    ],
    "accounting": [
        "dashboard.view",
        "accounting.view",
        "transactions.view",
        "bank_accounts.view",
        "profile.view",
        "profile.update",
        "profile.change_password",
    ],
    "marketing": [
        "dashboard.view",
        "coupons.view",
        "coupons.create",
        "coupons.update",
        "home_banner.view",
        "home_banner.update",
        "profile.view",
        "profile.update",
        "profile.change_password",
    ],
    "user": [
        "dashboard.view",
        "profile.view",
        "profile.update",
        "profile.change_password",
    ],
}


def _table_exists(conn, table: str) -> bool:
    row = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = :schema
              AND table_name = :table
            """
        ),
        {"schema": schema, "table": table},
    ).fetchone()
    return row is not None


def _column_exists(conn, table: str, column: str) -> bool:
    row = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name = :table
              AND column_name = :column
            """
        ),
        {"schema": schema, "table": table, "column": column},
    ).fetchone()
    return row is not None


def upgrade() -> None:
    conn = op.get_bind()

    if not _column_exists(conn, "auth_login", "must_change_password"):
        op.add_column(
            "auth_login",
            sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
            schema=schema,
        )
        op.alter_column("auth_login", "must_change_password", server_default=None, schema=schema)

    if not _table_exists(conn, "role_permission"):
        op.create_table(
            "role_permission",
            sa.Column("role", sa.String(length=20), nullable=False),
            sa.Column("permissions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("deleted", sa.Boolean(), nullable=False),
            sa.Column("enable", sa.Boolean(), nullable=False),
            sa.Column("created_by", sa.String(length=250), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("role", name="uq_role_permission_role"),
            schema=schema,
        )
        op.create_index(
            "ix_user_role_permission_role",
            "role_permission",
            ["role"],
            unique=False,
            schema=schema,
        )

    for role, permissions in role_permissions.items():
        conn.execute(
            sa.text(
                """
                INSERT INTO "user".role_permission
                    (id, role, permissions, deleted, enable, created_at, updated_at)
                VALUES
                    (:id, :role, CAST(:permissions AS jsonb), false, true, now(), now())
                ON CONFLICT (role) DO NOTHING
                """
            ),
            {"id": str(uuid.uuid4()), "role": role, "permissions": json.dumps(permissions)},
        )


def downgrade() -> None:
    conn = op.get_bind()
    if _table_exists(conn, "role_permission"):
        op.drop_index("ix_user_role_permission_role", table_name="role_permission", schema=schema)
        op.drop_table("role_permission", schema=schema)
    if _column_exists(conn, "auth_login", "must_change_password"):
        op.drop_column("auth_login", "must_change_password", schema=schema)
