"""Keep usernames in their dedicated field and constrain phone to digits."""
from alembic import op
import sqlalchemy as sa

revision = '102'
down_revision = '101'
branch_labels = None
depends_on = None


def upgrade():
    # Only remove a legacy handle when the independent field contains its copy.
    op.execute(sa.text('''
        UPDATE "user"."user" SET phone = NULL, updated_at = NOW()
        WHERE phone IS NOT NULL AND phone !~ '^[0-9]+$'
          AND whatsapp_username = '@' || ltrim(btrim(phone), '@')
    '''))
    # Formatting only: never discard letters or guess missing digits.
    op.execute(sa.text('''
        WITH normalized AS (
            SELECT id, translate(phone, E' +-().\\t\\n\\r' || chr(8234) || chr(8236) || chr(8206) || chr(8207), '') AS digits
            FROM "user"."user" WHERE phone IS NOT NULL
        )
        UPDATE "user"."user" AS u SET phone = n.digits, updated_at = NOW()
        FROM normalized AS n
        WHERE u.id = n.id AND u.phone <> n.digits AND n.digits ~ '^[0-9]+$'
    '''))
    op.create_check_constraint('ck_user_phone_digits', 'user', "phone IS NULL OR phone ~ '^[0-9]+$'", schema='user')


def downgrade():
    op.drop_constraint('ck_user_phone_digits', 'user', schema='user', type_='check')
    # Keep the cleaned contact data; do not put usernames back in phone.
