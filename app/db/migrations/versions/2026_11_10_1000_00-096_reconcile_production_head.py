"""Reconcile the Alembic head already recorded by the production database.

Production reported revision 096 while the repository stopped at 095. A schema
comparison found no missing model tables or columns; this revision restores
the migration graph without changing existing fiscal or customer data.
"""

revision = "096"
down_revision = "095"
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
