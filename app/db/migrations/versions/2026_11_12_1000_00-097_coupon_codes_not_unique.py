"""Allow separate coupons to share the same display code."""

from alembic import op


revision = "097"
down_revision = "096"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index("ix_transaction_coupons_code", table_name="coupons", schema="transaction")
    op.create_index("ix_transaction_coupons_code", "coupons", ["code"], unique=False,
                    schema="transaction")


def downgrade():
    # Restoring uniqueness requires removing duplicates first. Do not discard
    # coupons or silently choose one when rolling back.
    op.drop_index("ix_transaction_coupons_code", table_name="coupons", schema="transaction")
    op.create_index("ix_transaction_coupons_code", "coupons", ["code"], unique=True,
                    schema="transaction")
