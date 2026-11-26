"""Store WhatsApp usernames independently of telephone numbers.

Copy legacy @handles without changing phone, for compatibility with old clients.
"""
from alembic import op
import sqlalchemy as sa

revision = "101"
down_revision = "100"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("user", sa.Column("whatsapp_username", sa.String(100), nullable=True), schema="user")
    op.execute(sa.text('''
        UPDATE "user"."user"
        SET whatsapp_username = btrim(phone)
        WHERE btrim(phone) LIKE '@%'
    '''))


def downgrade():
    # Never discard a new username that cannot fit in the legacy phone field.
    # An operator must export/resolve those contacts before a destructive rollback.
    op.execute(sa.text('''
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM "user"."user"
                WHERE whatsapp_username IS NOT NULL
                  AND NULLIF(btrim(phone), '') IS NOT NULL
                  AND btrim(phone) <> whatsapp_username
            ) THEN
                RAISE EXCEPTION 'Cannot downgrade: users have independent phone and WhatsApp contacts';
            END IF;
        END $$;
    '''))
    op.execute(sa.text('''
        UPDATE "user"."user" SET phone = whatsapp_username
        WHERE whatsapp_username IS NOT NULL AND NULLIF(btrim(phone), '') IS NULL
    '''))
    op.drop_column("user", "whatsapp_username", schema="user")
