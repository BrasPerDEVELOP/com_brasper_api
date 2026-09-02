"""recompute accounting amounts with commission_accounting_settings

Revision ID: 077
Revises: 076
Create Date: 2026-09-02

Tras crear ``coin.commission_accounting_settings`` (076), recalcula los importes
contables de ``transaction.transactions`` con la regla operativa:

    si origin_amount = 0           → NULL
    si origin_amount < umbral      → fixed_commission (settings)
    si no                          → origin × percentage / 100  (tramo)

Cubre también envíos bajo el mínimo del catálogo (068 dejó fuera el tramo
``< 100`` a propósito): antes quedaban sin ``commission_accounting_id`` y la
073 los dejó en NULL. Ahora reciben la comisión fija del settings.

Idempotente: mismas entradas → mismas salidas.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "077"
down_revision: Union[str, None] = "076"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

IGV_RATE = "0.18"
MONEY_SCALE = 2
DEFAULT_THRESHOLD = "100"
DEFAULT_FIXED = "3"


def upgrade() -> None:
    conn = op.get_bind()

    updated = conn.execute(
        sa.text(
            f"""
            WITH settings AS (
                SELECT
                    COALESCE(
                        NULLIF(amount_threshold, 0),
                        {DEFAULT_THRESHOLD}::numeric
                    ) AS amount_threshold,
                    COALESCE(fixed_commission, {DEFAULT_FIXED}::numeric) AS fixed_commission
                FROM coin.commission_accounting_settings
                WHERE deleted IS false
                ORDER BY created_at ASC
                LIMIT 1
            ),
            defaults AS (
                SELECT
                    {DEFAULT_THRESHOLD}::numeric AS amount_threshold,
                    {DEFAULT_FIXED}::numeric AS fixed_commission
                WHERE NOT EXISTS (SELECT 1 FROM settings)
            ),
            rule AS (
                SELECT * FROM settings
                UNION ALL
                SELECT * FROM defaults
            ),
            computed AS (
                SELECT
                    t.id AS transaction_id,
                    CASE
                        WHEN t.origin_amount IS NULL OR t.origin_amount = 0 THEN NULL
                        WHEN t.origin_amount < r.amount_threshold
                            THEN ROUND(r.fixed_commission, {MONEY_SCALE})
                        WHEN ca.percentage IS NOT NULL
                            THEN ROUND(
                                t.origin_amount * ca.percentage / 100,
                                {MONEY_SCALE}
                            )
                        ELSE NULL
                    END AS commision
                FROM transaction.transactions AS t
                CROSS JOIN rule AS r
                LEFT JOIN coin.commission_accounting AS ca
                  ON ca.id = t.commission_accounting_id
                 AND ca.deleted IS false
                WHERE t.deleted IS false
            )
            UPDATE transaction.transactions AS t
            SET accounting_commision = c.commision,
                accounting_destination_amount = CASE
                    WHEN c.commision IS NULL THEN NULL
                    ELSE ROUND(t.origin_amount - c.commision, {MONEY_SCALE})
                END,
                accounting_tax_final = CASE
                    WHEN c.commision IS NULL THEN NULL
                    ELSE ROUND(c.commision * {IGV_RATE}, {MONEY_SCALE})
                END
            FROM computed AS c
            WHERE c.transaction_id = t.id
            """
        )
    ).rowcount

    under = conn.execute(
        sa.text(
            f"""
            WITH rule AS (
                SELECT
                    COALESCE(
                        (
                            SELECT NULLIF(amount_threshold, 0)
                            FROM coin.commission_accounting_settings
                            WHERE deleted IS false
                            ORDER BY created_at ASC
                            LIMIT 1
                        ),
                        {DEFAULT_THRESHOLD}::numeric
                    ) AS amount_threshold
            )
            SELECT count(*)
            FROM transaction.transactions AS t
            CROSS JOIN rule AS r
            WHERE t.deleted IS false
              AND t.origin_amount IS NOT NULL
              AND t.origin_amount > 0
              AND t.origin_amount < r.amount_threshold
              AND t.accounting_commision IS NOT NULL
            """
        )
    ).scalar_one()

    print(
        f"[077] importes contables recalculados: {updated} filas · "
        f"{under} bajo umbral con comisión fija"
    )


def downgrade() -> None:
    """Vuelve a la fórmula de la 073 (solo % del tramo; bajo umbral → NULL)."""
    conn = op.get_bind()
    conn.execute(
        sa.text(
            f"""
            WITH computed AS (
                SELECT
                    t.id AS transaction_id,
                    ROUND(t.origin_amount * ca.percentage / 100, {MONEY_SCALE}) AS commision
                FROM transaction.transactions AS t
                JOIN coin.commission_accounting AS ca
                  ON ca.id = t.commission_accounting_id
                WHERE ca.deleted IS false
            )
            UPDATE transaction.transactions AS t
            SET accounting_commision = c.commision,
                accounting_destination_amount = ROUND(
                    t.origin_amount - c.commision, {MONEY_SCALE}
                ),
                accounting_tax_final = ROUND(c.commision * {IGV_RATE}, {MONEY_SCALE})
            FROM computed AS c
            WHERE c.transaction_id = t.id
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE transaction.transactions
            SET accounting_commision = NULL,
                accounting_destination_amount = NULL,
                accounting_tax_final = NULL
            WHERE commission_accounting_id IS NULL
              AND (
                  accounting_commision IS NOT NULL
                  OR accounting_destination_amount IS NOT NULL
                  OR accounting_tax_final IS NOT NULL
              )
            """
        )
    )
