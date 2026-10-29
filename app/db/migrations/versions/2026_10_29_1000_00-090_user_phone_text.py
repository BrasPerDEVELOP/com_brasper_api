"""Store phone numbers and WhatsApp usernames without losing their text."""
from alembic import op
import sqlalchemy as sa

revision = "090"
down_revision = "089"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "user",
        "phone",
        schema="user",
        existing_type=sa.BigInteger(),
        type_=sa.String(100),
        existing_nullable=True,
        postgresql_using="phone::varchar(100)",
    )


def downgrade():
    # Refuse a rollback that would erase usernames or change phone formatting.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM "user"."user"
                WHERE phone IS NOT NULL AND CASE
                    WHEN phone ~ '^-?(0|[1-9][0-9]{0,18})$' THEN
                        phone::numeric < -9223372036854775808
                        OR phone::numeric > 9223372036854775807
                        OR phone::numeric::text <> phone
                    ELSE TRUE
                END
            ) THEN
                RAISE EXCEPTION 'Cannot downgrade phone: values cannot be represented as bigint without data loss';
            END IF;
        END $$;
    """)
    op.alter_column(
        "user",
        "phone",
        schema="user",
        existing_type=sa.String(100),
        type_=sa.BigInteger(),
        existing_nullable=True,
        postgresql_using="phone::bigint",
    )
