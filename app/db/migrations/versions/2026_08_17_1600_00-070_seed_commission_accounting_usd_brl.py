"""seed rangos de descuento USD -> BRL

Revision ID: 070
Revises: 069
Create Date: 2026-08-17 16:00:00.000000

Carga los 8 rangos de dólares a reales. La fórmula de origen reutiliza los
mismos cortes en soles, divididos entre 3.5 (el monto llega en dólares):

    =IF(N<100/3.5,0,IF(N<300/3.5,40%,IF(N<1000/3.5,45%,IF(N<2000/3.5,50%,
      IF(N<3000/3.5,55%,IF(N<5000/3.5,60%,IF(N<7000/3.5,65%,
      IF(N<10000/3.5,70%,75%))))))))

Los cocientes son decimales periódicos (100/3.5 = 28.5714285714...), así que
hay que ajustarlos a los 8 decimales de NUMERIC(20,8). Sólo 7000/3.5 = 2000 es
exacto.

El redondeo va **hacia arriba** (ROUND_CEILING), no al más cercano. Con el más
cercano, 6 de los 8 umbrales caen por debajo del valor real, y entonces el
propio valor almacenado (p. ej. 28.57142857) entra al tramo del 40% en la tabla
mientras la fórmula lo deja todavía en 0%. Redondeando hacia arriba, el umbral
guardado es el menor valor de 8 decimales >= al real, así que ningún monto
representable en NUMERIC(20,8) cae en la zona de discrepancia: tabla y fórmula
coinciden para todo valor que la base pueda almacenar.

Igual que en la 068 y la 069, el corte superior es EXCLUSIVO: se lee con
`min_amount <= x < max_amount`, y el tramo "menor al primer corte" (0%) no se
carga porque la ausencia de rango ya significa que no aplica descuento.

OJO: el 3.5 es un tipo de cambio congelado en la fórmula. Si cambia, estos 8
umbrales quedan desactualizados y hay que recalcularlos.
"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "070"
down_revision: Union[str, None] = "069"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

USD = "usd"
BRL = "brl"

# (min_amount, max_amount exclusivo, percentage). Valores = corte_en_soles / 3.5
# ajustados a 8 decimales hacia arriba. Como texto para no perder precisión.
DISCOUNT_RANGES: list[tuple[str, str | None, int]] = [
    ("28.57142858", "85.71428572", 40),      # 100/3.5  .. 300/3.5
    ("85.71428572", "285.71428572", 45),     # 300/3.5  .. 1000/3.5
    ("285.71428572", "571.42857143", 50),    # 1000/3.5 .. 2000/3.5
    ("571.42857143", "857.14285715", 55),    # 2000/3.5 .. 3000/3.5
    ("857.14285715", "1428.57142858", 60),   # 3000/3.5 .. 5000/3.5
    ("1428.57142858", "2000.00000000", 65),  # 5000/3.5 .. 7000/3.5 (exacto)
    ("2000.00000000", "2857.14285715", 70),  # 7000/3.5 .. 10000/3.5
    ("2857.14285715", None, 75),             # 10000/3.5 en adelante
]


def upgrade() -> None:
    conn = op.get_bind()

    for min_amount, max_amount, percentage in DISCOUNT_RANGES:
        conn.execute(
            sa.text(
                """
                INSERT INTO coin.commission_accounting
                    (id, coin_a, coin_b, percentage, reverse,
                     min_amount, max_amount, deleted, enable, created_at, updated_at)
                SELECT
                    :id, CAST(:coin_a AS coin.currency), CAST(:coin_b AS coin.currency),
                    :percentage, 0,
                    CAST(:min_amount AS numeric(20,8)),
                    CAST(:max_amount AS numeric(20,8)),
                    false, true, now(), now()
                WHERE NOT EXISTS (
                    SELECT 1 FROM coin.commission_accounting
                    WHERE coin_a = CAST(:coin_a AS coin.currency)
                      AND coin_b = CAST(:coin_b AS coin.currency)
                      AND min_amount = CAST(:min_amount AS numeric(20,8))
                      AND deleted = false
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "coin_a": USD,
                "coin_b": BRL,
                "percentage": percentage,
                "min_amount": min_amount,
                "max_amount": max_amount,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()

    for min_amount, max_amount, percentage in DISCOUNT_RANGES:
        conn.execute(
            sa.text(
                """
                DELETE FROM coin.commission_accounting
                WHERE coin_a = CAST(:coin_a AS coin.currency)
                  AND coin_b = CAST(:coin_b AS coin.currency)
                  AND min_amount = CAST(:min_amount AS numeric(20,8))
                  AND max_amount IS NOT DISTINCT FROM CAST(:max_amount AS numeric(20,8))
                  AND percentage = :percentage
                """
            ),
            {
                "coin_a": USD,
                "coin_b": BRL,
                "percentage": percentage,
                "min_amount": min_amount,
                "max_amount": max_amount,
            },
        )
