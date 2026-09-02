"""create coin.commission_accounting_settings (umbral + comisión fija)

Revision ID: 076
Revises: 075
Create Date: 2026-09-02

Singleton de configuración para Contabilidad:
si monto_envío < amount_threshold → fixed_commission (en vez del %).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "076"
down_revision: Union[str, None] = "075"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS coin.commission_accounting_settings (
                id UUID NOT NULL PRIMARY KEY,
                deleted BOOLEAN NOT NULL DEFAULT false,
                enable BOOLEAN NOT NULL DEFAULT true,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                created_by VARCHAR(250),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                amount_threshold NUMERIC(20, 8) NOT NULL DEFAULT 100,
                fixed_commission NUMERIC(20, 8) NOT NULL DEFAULT 3
            )
            """
        )
    )
    # Una sola fila activa de settings (semilla inicial).
    op.execute(
        sa.text(
            """
            INSERT INTO coin.commission_accounting_settings (
                id, deleted, enable, amount_threshold, fixed_commission
            )
            SELECT
                gen_random_uuid(),
                false,
                true,
                100,
                3
            WHERE NOT EXISTS (
                SELECT 1
                FROM coin.commission_accounting_settings
                WHERE deleted IS false
            )
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS coin.commission_accounting_settings"))
