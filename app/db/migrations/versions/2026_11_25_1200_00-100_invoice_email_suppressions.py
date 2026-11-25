"""Remember confirmed nonexistent fiscal email recipients."""
from alembic import op
import sqlalchemy as sa

revision = "100"
down_revision = "099"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('email_suppressions',
        sa.Column('email', sa.String(255), primary_key=True),
        sa.Column('reason', sa.String(40), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema='billing')


def downgrade():
    op.drop_table('email_suppressions', schema='billing')
