"""add_blog_permissions

Revision ID: 049
Revises: e990d42abded
Create Date: 2026-05-20 20:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '049'
down_revision: Union[str, None] = 'e990d42abded'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    # update admin role to add blog permissions
    conn.execute(sa.text("""
        UPDATE "user".role_permission
        SET permissions = permissions || '["blog.view", "blog.create", "blog.update", "blog.delete"]'::jsonb
        WHERE role = 'admin'
    """))
    # update marketing role to add blog permissions
    conn.execute(sa.text("""
        UPDATE "user".role_permission
        SET permissions = permissions || '["blog.view", "blog.create", "blog.update", "blog.delete"]'::jsonb
        WHERE role = 'marketing'
    """))


def downgrade() -> None:
    conn = op.get_bind()
    # remove blog permissions on downgrade
    conn.execute(sa.text("""
        UPDATE "user".role_permission
        SET permissions = permissions - 'blog.view' - 'blog.create' - 'blog.update' - 'blog.delete'
        WHERE role IN ('admin', 'marketing')
    """))
