"""Separate Omie NFS-e attempts from SUNAT documents and series."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
revision = "095"
down_revision = "094"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("omie_invoices",
        sa.Column("transaction_id", UUID(as_uuid=True), sa.ForeignKey("transaction.transactions.id"), primary_key=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("total", sa.Numeric(20, 2), nullable=False),
        sa.Column("os_id", sa.BigInteger(), nullable=True),
        sa.Column("nfse_id", sa.BigInteger(), nullable=True),
        sa.Column("nfse_number", sa.String(30), nullable=True),
        sa.Column("snapshot", JSONB(), nullable=False),
        sa.Column("error", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), schema="billing")


def downgrade():
    op.drop_table("omie_invoices", schema="billing")
