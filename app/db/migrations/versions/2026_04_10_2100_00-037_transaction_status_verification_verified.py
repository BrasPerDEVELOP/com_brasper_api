"""transaction_status_verification_verified

Revision ID: 037
Revises: 995e8abd8eac
Create Date: 2026-04-10

Añade 'verification' y 'verified' al enum transaction_status; migra 'checked' -> 'verified';
default de columna status -> 'verification'.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "037"
down_revision: Union[str, None] = "995e8abd8eac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "transaction"


def upgrade() -> None:
    op.execute(f"ALTER TYPE {schema}.transaction_status ADD VALUE 'verification'")
    op.execute(f"ALTER TYPE {schema}.transaction_status ADD VALUE 'verified'")
    op.execute(
        f"""
        UPDATE {schema}.transactions
        SET status = 'verified'
        WHERE status = 'checked'
        """
    )
    op.execute(
        f"""
        ALTER TABLE {schema}.transactions
        ALTER COLUMN status SET DEFAULT 'verification'
        """
    )


def downgrade() -> None:
    op.execute(
        f"ALTER TABLE {schema}.transactions ALTER COLUMN status SET DEFAULT 'pending'"
    )
    # No se eliminan valores del enum en PostgreSQL de forma trivial.
