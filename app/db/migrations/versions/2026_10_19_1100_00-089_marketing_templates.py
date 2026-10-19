"""Persist the template chosen for each campaign; retain legacy messages."""
from alembic import op
import sqlalchemy as sa

revision = "089"
down_revision = "088"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("marketing_campaigns", sa.Column("template_key", sa.String(50), nullable=True))


def downgrade():
    op.drop_column("marketing_campaigns", "template_key")
