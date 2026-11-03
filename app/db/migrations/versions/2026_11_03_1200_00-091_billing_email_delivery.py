"""Track optional invoice PDF delivery by email after acceptance."""
from alembic import op
import sqlalchemy as sa

revision = "091"
down_revision = "090"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("invoices", sa.Column("email_requested", sa.Boolean(), nullable=False, server_default=sa.false()), schema="billing")
    op.add_column("invoices", sa.Column("email_status", sa.String(20), nullable=True), schema="billing")
    op.add_column("invoices", sa.Column("email_sent_at", sa.DateTime(timezone=True), nullable=True), schema="billing")
    op.create_index("ix_billing_invoice_email_pending", "invoices", ["email_status"], schema="billing", postgresql_where=sa.text("email_status = 'pending' AND status = 'accepted' AND deleted = false"))


def downgrade():
    op.drop_index("ix_billing_invoice_email_pending", table_name="invoices", schema="billing")
    for name in ("email_sent_at", "email_status", "email_requested"):
        op.drop_column("invoices", name, schema="billing")
