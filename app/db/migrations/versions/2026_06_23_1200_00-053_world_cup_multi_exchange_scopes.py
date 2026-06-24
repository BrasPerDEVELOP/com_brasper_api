"""world cup coupons support multiple exchange-rate scopes

Revision ID: 053
Revises: 052
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "053"
down_revision: Union[str, None] = "052"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "campaign",
        sa.Column(
            "exchange_rate_scopes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[\"PEN_BRL\"]'::jsonb"),
        ),
        schema="world_cup",
    )
    op.execute(
        """
        UPDATE world_cup.campaign
        SET exchange_rate_scopes = CASE
            WHEN origin_currency = 'ALL' OR destination_currency = 'ALL'
                THEN '["ALL"]'::jsonb
            ELSE jsonb_build_array(origin_currency || '_' || destination_currency)
        END
        """
    )
    op.alter_column(
        "campaign",
        "exchange_rate_scopes",
        server_default=None,
        schema="world_cup",
    )

    op.add_column(
        "coupons",
        sa.Column("exchange_rate_scopes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema="transaction",
    )
    op.execute(
        """
        UPDATE transaction.coupons
        SET exchange_rate_scopes = CASE
            WHEN origin_currency IS NULL OR destination_currency IS NULL
                THEN '["ALL"]'::jsonb
            ELSE jsonb_build_array(upper(origin_currency::text) || '_' || upper(destination_currency::text))
        END
        WHERE coupon_type = 'MATCH'
        """
    )


def downgrade() -> None:
    op.drop_column("coupons", "exchange_rate_scopes", schema="transaction")
    op.drop_column("campaign", "exchange_rate_scopes", schema="world_cup")
