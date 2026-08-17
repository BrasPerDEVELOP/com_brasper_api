"""calcula los importes contables de transaction.transactions

Revision ID: 073
Revises: 072
Create Date: 2026-08-17 19:00:00.000000

Rellena las tres columnas contables a partir del tramo ya vinculado por la 072
(`commission_accounting_id`) y de `origin_amount`:

    pct = commission_accounting.percentage        -- entero: 45 = 45%

    accounting_commision          = ROUND(origin_amount * pct / 100, 2)
    accounting_destination_amount = ROUND(origin_amount - accounting_commision, 2)
    accounting_tax_final          = ROUND(accounting_commision * 0.18, 2)

Notas sobre la fórmula, decidida por negocio:

- El porcentaje del tramo se aplica DIRECTO sobre `origin_amount`. No es un
  descuento sobre la comisión comercial (`commission_id`), que es la otra lectura
  posible de `percentage`. Con los tramos actuales (40%-75%) eso da comisiones
  altas respecto del envío: 500 con el tramo del 45% deja 225 de comisión.
- `accounting_destination_amount` es una resta en MONEDA DE ORIGEN: no se
  multiplica por la tasa. No es comparable con `destination_amount`, que sí está
  en moneda de destino.
- El IGV se AÑADE sobre la comisión (18%), no se extrae de ella.

`accounting_destination_amount` y `accounting_tax_final` se derivan de la comisión
ya redondeada, así que comisión + destino suman exactamente `origin_amount`.

Alcance: todas las filas con `commission_accounting_id`. Las que quedaron sin
tramo en la 072 (envíos menores al mínimo del par, pares sin sembrar) siguen en
NULL: sin tramo no hay porcentaje del que derivar nada.

Idempotente por recálculo: mismas entradas, mismas salidas. Recalcula también las
filas que ya tengan valores, para que la tabla quede coherente con una sola
fórmula (hoy están todas en NULL, así que no pisa nada cargado a mano).
"""

from alembic import op
import sqlalchemy as sa

revision = "073"
down_revision = "072"
branch_labels = None
depends_on = None

#: IGV sobre la comisión contable. Reemplaza el 0.18 que el backoffice calculaba
#: en el navegador (contabilidad_view.vue, IMPUESTO_INTERNO_RATE).
IGV_RATE = "0.18"

#: Decimales de los importes, igual que `_money()` en los casos de uso.
MONEY_SCALE = 2


def upgrade() -> None:
    conn = op.get_bind()

    computed = conn.execute(
        sa.text(
            f"""
            WITH computed AS (
                SELECT
                    t.id AS transaction_id,
                    ROUND(t.origin_amount * ca.percentage / 100, {MONEY_SCALE}) AS commision
                FROM transaction.transactions AS t
                JOIN coin.commission_accounting AS ca
                  ON ca.id = t.commission_accounting_id
                WHERE ca.deleted IS FALSE
            )
            UPDATE transaction.transactions AS t
            SET accounting_commision          = c.commision,
                accounting_destination_amount = ROUND(
                    t.origin_amount - c.commision, {MONEY_SCALE}
                ),
                accounting_tax_final          = ROUND(
                    c.commision * {IGV_RATE}, {MONEY_SCALE}
                )
            FROM computed AS c
            WHERE c.transaction_id = t.id
            """
        )
    ).rowcount

    pending = conn.execute(
        sa.text(
            """
            SELECT count(*)
            FROM transaction.transactions
            WHERE accounting_commision IS NULL
              AND deleted IS FALSE
            """
        )
    ).scalar_one()

    print(
        f"[073] importes contables: {computed} transacciones calculadas · "
        f"{pending} activas sin tramo (quedan en NULL)"
    )


def downgrade() -> None:
    # Nada más escribe estas columnas todavía -- ni el alta ni la edición las
    # tocan --, así que limpiarlas revierte exactamente lo que hizo el upgrade.
    op.execute(
        sa.text(
            """
            UPDATE transaction.transactions
            SET accounting_commision = NULL,
                accounting_destination_amount = NULL,
                accounting_tax_final = NULL
            WHERE accounting_commision IS NOT NULL
               OR accounting_destination_amount IS NOT NULL
               OR accounting_tax_final IS NOT NULL
            """
        )
    )
