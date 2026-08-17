"""seed coin.commission_accounting con los rangos de descuento PEN -> BRL

Revision ID: 068
Revises: 067
Create Date: 2026-08-17 14:00:00.000000

Carga los 8 rangos de descuento de soles a reales. `percentage` se guarda como
entero (40 = 40%), igual que `coupon_discount_percentage` en el módulo de
transacciones. El último rango deja `max_amount` en NULL ("10 mil a más").

El tramo "menores a 100 -- 3 soles/reales" queda fuera a propósito: es un monto
fijo, no un porcentaje, y no tiene columna donde representarse sin que quien lea
`percentage` lo interprete mal.

Idempotente: cada fila se inserta solo si no existe ya un registro activo con la
misma combinación (coin_a, coin_b, min_amount, max_amount).
"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "068"
down_revision: Union[str, None] = "067"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Las etiquetas del ENUM coin.currency son minúsculas ('pen', 'brl', 'usd') y
# SQLAlchemy persiste el *nombre* del miembro de Currency, no su valor.
COIN_A = "pen"
COIN_B = "brl"

# (min_amount, max_amount, percentage) — max_amount None = sin límite superior.
DISCOUNT_RANGES: list[tuple[int, int | None, int]] = [
    (100, 299, 40),
    (300, 999, 45),
    (1000, 1999, 50),
    (2000, 2999, 55),
    (3000, 4999, 60),
    (5000, 6999, 65),
    (7000, 9999, 70),
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
                      AND max_amount IS NOT DISTINCT FROM :max_amount
                      AND deleted = false
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "coin_a": COIN_A,
                "coin_b": COIN_B,
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
                "coin_a": COIN_A,
                "coin_b": COIN_B,
                "percentage": percentage,
                "min_amount": min_amount,
                "max_amount": max_amount,
            },
        )
