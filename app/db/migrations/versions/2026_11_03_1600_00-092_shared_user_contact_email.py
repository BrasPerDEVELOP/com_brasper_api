"""Permitir correos de contacto compartidos, conservando usernames únicos.

Revision ID: 092
Revises: 091
"""
from alembic import op

revision = "092"
down_revision = "091"
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE "user"."user" DROP CONSTRAINT IF EXISTS user_email_key')
    for name in ("uq_user_email_alive", "ix_user_user_email", "user_email_key"):
        op.execute(f'DROP INDEX IF EXISTS "user"."{name}"')
    op.create_index("ix_user_email_alive", "user", ["email"], schema="user",
                    unique=False, postgresql_where="deleted = false AND email IS NOT NULL")


def downgrade():
    # Falla sin alterar datos si ya hay correos compartidos. Nunca borrar clientes.
    op.create_index("uq_user_email_alive", "user", ["email"], schema="user",
                    unique=True, postgresql_where="deleted = false AND email IS NOT NULL")
    op.drop_index("ix_user_email_alive", table_name="user", schema="user")
