"""Persist the exact SUNAT invoice line description used by branded PDFs.

Revision ID: 098
Revises: 097
"""
from alembic import op
import sqlalchemy as sa

revision = "098"
down_revision = "097"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("invoices", sa.Column("item_description", sa.Text(), nullable=True), schema="billing")


def downgrade():
    op.drop_column("invoices", "item_description", schema="billing")
