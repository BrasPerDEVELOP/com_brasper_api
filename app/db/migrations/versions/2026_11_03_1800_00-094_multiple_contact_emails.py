"""Multiple contact emails and per-recipient PDF delivery history.

Revision ID: 094
Revises: 093
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "094"
down_revision = "093"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("user", sa.Column("emails", JSONB(), nullable=False, server_default="[]"), schema="user")
    op.execute('UPDATE "user"."user" SET emails = jsonb_build_array(email) WHERE email IS NOT NULL AND trim(email) <> \'\'')
    for name in ("email_recipients", "email_delivered_to"):
        op.add_column("invoices", sa.Column(name, JSONB(), nullable=False, server_default="[]"), schema="billing")
    op.execute("UPDATE billing.invoices SET email_recipients = jsonb_build_array(customer_email) WHERE email_requested AND customer_email IS NOT NULL")
    op.execute("UPDATE billing.invoices SET email_delivered_to = email_recipients WHERE email_status = 'sent'")


def downgrade():
    op.drop_column("invoices", "email_delivered_to", schema="billing")
    op.drop_column("invoices", "email_recipients", schema="billing")
    op.drop_column("user", "emails", schema="user")
