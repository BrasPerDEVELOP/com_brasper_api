"""create_bank_accounts_table

Revision ID: 013
Revises: 012
Create Date: 2025-01-30

Crea tipos account_flow_type, account_holder_type y tabla transaction.bank_accounts
(user_id, bank_id, titular, empresarial, cuenta Perú, PIX/Brasil).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

schema = "transaction"


def upgrade() -> None:
    op.execute(sa.text(
        "CREATE TYPE transaction.account_flow_type AS ENUM ('origin', 'destination')"
    ))
    op.execute(sa.text(
        "CREATE TYPE transaction.account_holder_type AS ENUM ('personal', 'legal')"
    ))
    op.execute(sa.text("""
        CREATE TABLE transaction.bank_accounts (
            id UUID NOT NULL PRIMARY KEY,
            deleted BOOLEAN NOT NULL DEFAULT false,
            enable BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            created_by VARCHAR(250),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            user_id UUID NOT NULL REFERENCES "user".user(id),
            bank_id UUID NOT NULL REFERENCES transaction.banks(id),
            account_flow transaction.account_flow_type NOT NULL,
            account_holder_type transaction.account_holder_type NOT NULL,
            bank_country transaction.bank_country NOT NULL,
            holder_names VARCHAR(255),
            holder_surnames VARCHAR(255),
            document_number VARCHAR(20),
            business_name VARCHAR(255),
            ruc_number VARCHAR(20),
            legal_representative_name VARCHAR(255),
            legal_representative_document VARCHAR(20),
            account_number VARCHAR(255),
            account_number_confirmation VARCHAR(255),
            cci_number VARCHAR(255),
            cci_number_confirmation VARCHAR(255),
            pix_key VARCHAR(255),
            pix_key_confirmation VARCHAR(255),
            pix_key_type VARCHAR(50),
            cpf VARCHAR(14)
        )
    """))
    op.create_index(
        op.f("ix_transaction_bank_accounts_user_id"),
        "bank_accounts",
        ["user_id"],
        schema=schema,
    )
    op.create_index(
        op.f("ix_transaction_bank_accounts_bank_id"),
        "bank_accounts",
        ["bank_id"],
        schema=schema,
    )
    op.create_index(
        op.f("ix_transaction_bank_accounts_account_flow"),
        "bank_accounts",
        ["account_flow"],
        schema=schema,
    )
    op.create_index(
        op.f("ix_transaction_bank_accounts_account_holder_type"),
        "bank_accounts",
        ["account_holder_type"],
        schema=schema,
    )
    op.create_index(
        op.f("ix_transaction_bank_accounts_bank_country"),
        "bank_accounts",
        ["bank_country"],
        schema=schema,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_transaction_bank_accounts_bank_country"),
        table_name="bank_accounts",
        schema=schema,
    )
    op.drop_index(
        op.f("ix_transaction_bank_accounts_account_holder_type"),
        table_name="bank_accounts",
        schema=schema,
    )
    op.drop_index(
        op.f("ix_transaction_bank_accounts_account_flow"),
        table_name="bank_accounts",
        schema=schema,
    )
    op.drop_index(
        op.f("ix_transaction_bank_accounts_bank_id"),
        table_name="bank_accounts",
        schema=schema,
    )
    op.drop_index(
        op.f("ix_transaction_bank_accounts_user_id"),
        table_name="bank_accounts",
        schema=schema,
    )
    op.drop_table("bank_accounts", schema=schema)
    op.execute(sa.text("DROP TYPE IF EXISTS transaction.account_holder_type CASCADE"))
    op.execute(sa.text("DROP TYPE IF EXISTS transaction.account_flow_type CASCADE"))
