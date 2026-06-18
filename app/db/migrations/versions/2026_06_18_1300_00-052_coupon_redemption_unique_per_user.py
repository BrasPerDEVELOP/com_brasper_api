"""backstop unique partial index for per-user coupon redemptions

Revision ID: 052
Revises: 051

DB-level safeguard for ``per_user_limit == 1``. The application already serializes
redemptions via ``SELECT ... FOR UPDATE`` on the coupon row and recomputes the
discount server-side (see ``transaction_use_cases._apply_server_financials``),
but a partial UNIQUE index on ``(coupon_id, user_id) WHERE deleted = false``
guarantees a single live redemption per (coupon, user) even under a race or a
buggy/bypassed code path.

Why partial (``WHERE deleted = false``): redemptions are soft-deleted
(``ORMBaseModel.deleted``) when a transaction is cancelled and the coupon usage
is released. A soft-deleted row must not block a later legitimate redemption,
so only live rows participate in the uniqueness constraint.

NOTE: migration 050 already created a NON-unique index
``ix_coupon_redemptions_coupon_user`` on the same columns for lookup speed. This
revision is additive and does not touch it: that index speeds up the
``per_user_limit`` count query; this one enforces uniqueness. They are not
duplicates.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "052"
down_revision: Union[str, None] = "051"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INDEX_NAME = "uq_coupon_redemptions_coupon_user_live"
TABLE_NAME = "coupon_redemptions"
SCHEMA = "world_cup"


def upgrade() -> None:
    op.create_index(
        INDEX_NAME,
        TABLE_NAME,
        ["coupon_id", "user_id"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("deleted = false"),
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name=TABLE_NAME, schema=SCHEMA)
