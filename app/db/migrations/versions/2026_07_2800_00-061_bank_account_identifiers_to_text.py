"""bank account identifiers to text

Revision ID: 061
Revises: 060
Create Date: 2026-07-28

Los números de cuenta, CCI y documentos son identificadores, no cantidades.
VARCHAR conserva ceros iniciales y evita pérdida de precisión en valores largos.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "061"
down_revision: Union[str, None] = "060"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "transaction"
table = "bank_accounts"
identifier_columns = (
    "document_number",
    "ruc_number",
    "legal_representative_document",
    "account_number",
    "cci_number",
    "cpf",
)


def upgrade() -> None:
    for column in identifier_columns:
        op.execute(
            sa.text(
                f"ALTER TABLE {schema}.{table} "
                f"ALTER COLUMN {column} TYPE VARCHAR(255) "
                f"USING {column}::TEXT"
            )
        )


def downgrade() -> None:
    for column in identifier_columns:
        op.execute(
            sa.text(
                f"ALTER TABLE {schema}.{table} "
                f"ALTER COLUMN {column} TYPE BIGINT "
                f"USING NULLIF(TRIM({column}), '')::BIGINT"
            )
        )
