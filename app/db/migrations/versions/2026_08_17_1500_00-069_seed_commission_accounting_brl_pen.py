"""seed rangos de descuento BRL -> PEN y alinea los cortes de PEN -> BRL

Revision ID: 069
Revises: 068
Create Date: 2026-08-17 15:00:00.000000

Carga los 8 rangos de reales a soles y, de paso, corrige la convención de
`max_amount` de la dirección PEN -> BRL que sembró la 068.

La fórmula de origen usa cortes con `<` estricto:

    =IF(N<100,0,IF(N<300,40%,IF(N<1000,45%,IF(N<2000,50%,IF(N<3000,55%,
      IF(N<5000,60%,IF(N<7000,65%,IF(N<10000,70%,75%))))))))

Es decir el tramo del 40% es [100, 300), no [100, 299]. La 068 guardó
max_amount = 299, 999, 1999... y eso dejaba sin rango los montos decimales
(299.50 no caía en ningún tramo y habría cobrado 0%). Aquí ambas direcciones
quedan con el corte superior EXCLUSIVO: se lee con `min_amount <= x < max_amount`.

El tramo "menor a 100" (0%) no se carga, igual que en la 068: la ausencia de
rango ya significa que no aplica descuento.
"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "069"
down_revision: Union[str, None] = "068"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Etiquetas del ENUM coin.currency (minúsculas: SQLAlchemy persiste el nombre
# del miembro de Currency, no su valor).
PEN = "pen"
BRL = "brl"

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

# Corrección de la 068: max_amount inclusivo -> exclusivo, por min_amount.
PEN_BRL_MAX_FIX: list[tuple[int, int, int]] = [
    # (min_amount, max viejo, max nuevo)
    (100, 299, 300),
    (300, 999, 1000),
    (1000, 1999, 2000),
    (2000, 2999, 3000),
    (3000, 4999, 5000),
    (5000, 6999, 7000),
    (7000, 9999, 10000),
]

_INSERT = sa.text(
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
)


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Alinear los cortes de PEN -> BRL sembrados por la 068.
    for min_amount, old_max, new_max in PEN_BRL_MAX_FIX:
        conn.execute(
            sa.text(
                """
                UPDATE coin.commission_accounting
                SET max_amount = :new_max, updated_at = now()
                WHERE coin_a = CAST(:pen AS coin.currency)
                  AND coin_b = CAST(:brl AS coin.currency)
                  AND min_amount = :min_amount
                  AND max_amount = :old_max
                  AND deleted = false
                """
            ),
            {"pen": PEN, "brl": BRL, "min_amount": min_amount,
             "old_max": old_max, "new_max": new_max},
        )

    # 2. Sembrar la dirección BRL -> PEN.
    for min_amount, max_amount, percentage in DISCOUNT_RANGES:
        conn.execute(
            _INSERT,
            {
                "id": str(uuid.uuid4()),
                "coin_a": BRL,
                "coin_b": PEN,
                "percentage": percentage,
                "min_amount": min_amount,
                "max_amount": max_amount,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()

    # Quitar BRL -> PEN.
    for min_amount, max_amount, percentage in DISCOUNT_RANGES:
        conn.execute(
            sa.text(
                """
                DELETE FROM coin.commission_accounting
                WHERE coin_a = CAST(:brl AS coin.currency)
                  AND coin_b = CAST(:pen AS coin.currency)
                  AND min_amount = :min_amount
                  AND max_amount IS NOT DISTINCT FROM :max_amount
                  AND percentage = :percentage
                """
            ),
            {"brl": BRL, "pen": PEN, "min_amount": min_amount,
             "max_amount": max_amount, "percentage": percentage},
        )

    # Devolver PEN -> BRL a los cortes inclusivos de la 068.
    for min_amount, old_max, new_max in PEN_BRL_MAX_FIX:
        conn.execute(
            sa.text(
                """
                UPDATE coin.commission_accounting
                SET max_amount = :old_max, updated_at = now()
                WHERE coin_a = CAST(:pen AS coin.currency)
                  AND coin_b = CAST(:brl AS coin.currency)
                  AND min_amount = :min_amount
                  AND max_amount = :new_max
                  AND deleted = false
                """
            ),
            {"pen": PEN, "brl": BRL, "min_amount": min_amount,
             "old_max": old_max, "new_max": new_max},
        )
