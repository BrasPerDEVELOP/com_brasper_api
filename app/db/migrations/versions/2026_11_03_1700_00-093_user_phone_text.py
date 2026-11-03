"""Store phone numbers and @usernames without losing existing numbers."""
from alembic import op
import sqlalchemy as sa

revision = "093"
down_revision = "092"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "user", "phone", schema="user",
        existing_type=sa.BigInteger(), type_=sa.String(100),
        existing_nullable=True, postgresql_using="phone::text",
    )


def downgrade():
    # Never silently discard handles or leading zeroes on rollback.
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM "user"."user"
                WHERE phone IS NOT NULL AND phone !~ '^(0|-?[1-9][0-9]*)$'
            ) THEN
                RAISE EXCEPTION 'Cannot restore numeric phone without losing text or leading zeroes';
            END IF;
        END $$;
    """)
    op.alter_column(
        "user", "phone", schema="user",
        existing_type=sa.String(100), type_=sa.BigInteger(),
        existing_nullable=True, postgresql_using="phone::bigint",
    )
