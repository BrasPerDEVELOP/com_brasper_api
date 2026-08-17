"""backfill transaction.transactions.commission_accounting_id por rango

Revision ID: 072
Revises: 071
Create Date: 2026-08-17 18:00:00.000000

Asigna a cada transacción el tramo de `coin.commission_accounting` que le
corresponde: mismo par de monedas que su `tax_rate` y `origin_amount` dentro del
rango. Los rangos que siembran las migraciones 068-071 están expresados en moneda
de origen, así que `origin_amount` es el monto que decide; `destination_amount` no
interviene (tampoco lo hace en `_apply_server_financials`, que es como el servidor
elige el tramo al cotizar).

El corte superior es EXCLUSIVO -- `min_amount <= origin_amount < max_amount` --,
la convención que fijó la 069 al alinear los cortes con la fórmula original
(`IF(N<300, 40%, IF(N<1000, 45%, ...))`). Por eso 300 cae en el tramo del 45% y
no en el del 40%. Un `max_amount` NULL es sin límite superior.

OJO al reutilizar esta regla: `_apply_server_financials` compara con
`amount <= max_amount` (inclusivo) porque lee `coin.commission`, que sí usa esa
convención. Las dos tablas no la comparten.

Solo toca filas con la FK en NULL: nunca reasigna un vínculo ya establecido.
Las transacciones que no caen en ningún tramo quedan en NULL a propósito; esta
migración no aproxima al tramo más cercano. Los dos casos esperados son:

- `origin_amount` menor al mínimo del par (los envíos de menos de 100, que el
  catálogo cobra con tarifa fija y por eso 068 dejó fuera);
- pares sin sembrar (068-071 cubren pen->brl, brl->pen, usd->brl y brl->usd).

Idempotente: reejecutarla solo alcanza a las que sigan en NULL.
"""

from alembic import op
import sqlalchemy as sa

revision = "072"
down_revision = "071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    linked = conn.execute(
        sa.text(
            """
            WITH resolved AS (
                SELECT
                    t.id AS transaction_id,
                    (
                        SELECT ca.id
                        FROM coin.commission_accounting AS ca
                        JOIN coin.tax_rate AS tr ON tr.id = t.tax_rate_id
                        WHERE ca.deleted IS FALSE
                          AND ca.coin_a = tr.coin_a
                          AND ca.coin_b = tr.coin_b
                          AND (ca.min_amount IS NULL OR t.origin_amount >= ca.min_amount)
                          AND (ca.max_amount IS NULL OR t.origin_amount < ca.max_amount)
                        ORDER BY ca.min_amount NULLS FIRST, ca.max_amount NULLS LAST
                        LIMIT 1
                    ) AS commission_accounting_id
                FROM transaction.transactions AS t
                WHERE t.commission_accounting_id IS NULL
            )
            UPDATE transaction.transactions AS t
            SET commission_accounting_id = r.commission_accounting_id
            FROM resolved AS r
            WHERE r.transaction_id = t.id
              AND r.commission_accounting_id IS NOT NULL
            """
        )
    ).rowcount

    pending = conn.execute(
        sa.text(
            """
            SELECT count(*)
            FROM transaction.transactions
            WHERE commission_accounting_id IS NULL
              AND deleted IS FALSE
            """
        )
    ).scalar_one()

    print(
        f"[072] commission_accounting_id: {linked} transacciones vinculadas · "
        f"{pending} activas sin tramo (quedan en NULL)"
    )


def downgrade() -> None:
    # Hoy nada más escribe esta columna -- ni el alta ni la edición la tocan --,
    # así que limpiarla entera revierte exactamente lo que hizo el upgrade.
    op.execute(
        sa.text(
            "UPDATE transaction.transactions SET commission_accounting_id = NULL "
            "WHERE commission_accounting_id IS NOT NULL"
        )
    )
