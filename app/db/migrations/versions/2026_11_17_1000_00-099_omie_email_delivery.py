"""Track queued NFS-e PDF email deliveries independently of SUNAT."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "099"
down_revision = "098"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("omie_invoices", sa.Column("email_status", sa.String(20), nullable=True), schema="billing")
    op.add_column("omie_invoices", sa.Column("email_error", sa.String(600), nullable=True), schema="billing")
    for name in ("email_recipients", "email_delivered_to"):
        op.add_column("omie_invoices", sa.Column(name, JSONB(), nullable=False, server_default="[]"), schema="billing")
    op.add_column("omie_invoices", sa.Column("email_sent_at", sa.DateTime(timezone=True), nullable=True), schema="billing")


def downgrade():
    for name in ("email_sent_at", "email_delivered_to", "email_recipients", "email_error", "email_status"):
        op.drop_column("omie_invoices", name, schema="billing")
