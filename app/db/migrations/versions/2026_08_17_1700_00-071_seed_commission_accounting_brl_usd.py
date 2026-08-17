"""seed rangos de descuento BRL -> USD

Revision ID: 071
Revises: 070
Create Date: 2026-08-17 17:00:00.000000

Carga los 8 rangos de reales a dólares:

    =IF(N<100,0,IF(N<300,40%,IF(N<1000,45%,IF(N<2000,50%,IF(N<3000,55%,
      IF(N<5000,60%,IF(N<7000,65%,IF(N<10000,70%,75%))))))))

Los cortes son los mismos enteros que en BRL -> PEN (la 069): el tramo se
decide sobre el monto de origen en reales, así que no hay conversión. A
diferencia de USD -> BRL (la 070, con los umbrales divididos entre 3.5), aquí
todos los valores son exactos en NUMERIC(20,8).

Corte superior EXCLUSIVO, igual que 068/069/070: se lee con
`min_amount <= x < max_amount`. El tramo "menor a 100" (0%) no se carga porque
la ausencia de rango ya significa que no aplica descuento.
"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "071"
down_revision: Union[str, None] = "070"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BRL = "brl"
USD = "usd"

# (min_amount, max_amount exclusivo, percentage) — max None = sin límite.
DISCOUNT_RANGES: list[tuple[int, int | None, int]] = [
    (100, 300, 40),
    (300, 1000, 45),
    (1000, 2000, 50),
    (2000, 3000, 55),
    (3000, 5000, 60),
    (5000, 7000, 65),
    (7000, 10000, 70),
    (10000, None, 75),
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
                    :percentage, 0, :min_amount, :max_amount, false, true, now(), now()
                WHERE NOT EXISTS (
                    SELECT 1 FROM coin.commission_accounting
                    WHERE coin_a = CAST(:coin_a AS coin.currency)
                      AND coin_b = CAST(:coin_b AS coin.currency)
                      AND min_amount = :min_amount
                      AND deleted = false
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "coin_a": BRL,
                "coin_b": USD,
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
                  AND min_amount = :min_amount
                  AND max_amount IS NOT DISTINCT FROM :max_amount
                  AND percentage = :percentage
                """
            ),
            {
                "coin_a": BRL,
                "coin_b": USD,
                "percentage": percentage,
                "min_amount": min_amount,
                "max_amount": max_amount,
            },
        )
