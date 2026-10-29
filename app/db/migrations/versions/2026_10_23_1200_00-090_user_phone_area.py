"""Add optional telephone area and country to users without guessing residence."""
from alembic import op
import sqlalchemy as sa

revision = "090"
down_revision = "089"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("user", sa.Column("local_area_code", sa.String(6), nullable=True), schema="user")
    op.add_column("user", sa.Column("local_area_name", sa.String(150), nullable=True), schema="user")
    op.add_column("user", sa.Column("country", sa.String(100), nullable=True), schema="user")


def downgrade():
    for name in ("country", "local_area_name", "local_area_code"):
        op.drop_column("user", name, schema="user")
