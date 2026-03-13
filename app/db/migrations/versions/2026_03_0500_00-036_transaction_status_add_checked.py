"""transaction_status_add_checked

Revision ID: 036
Revises: 035
Create Date: 2026-03-05

Añade valor 'checked' al enum transaction_status.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "036"
down_revision: Union[str, None] = "035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "transaction"


def upgrade() -> None:
    op.execute(
        f"ALTER TYPE {schema}.transaction_status ADD VALUE 'checked'"
    )


def downgrade() -> None:
    # PostgreSQL no permite eliminar valores de enum fácilmente.
    # Se deja vacío; en caso necesario recrear el tipo.
    pass
