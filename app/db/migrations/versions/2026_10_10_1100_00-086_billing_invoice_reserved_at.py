"""billing.invoices.reserved_at: momento en que el comprobante pasó a ``reserved``.

Lo usa el poller para detectar comprobantes atascados en ``reserved`` (el
proceso se cayó entre reservar el número y llamar a APISUNAT). No se reutiliza
``created_at``/``updated_at`` porque su ``server_default`` aplica
``now() AT TIME ZONE 'America/Lima'`` sobre una columna ``timestamptz`` y, con
la sesión de Postgres en UTC, quedan desplazados 5 horas: un comprobante recién
reservado parecería viejo y se "recuperaría" en pleno envío.

Revision ID: 086
Revises: 085
"""
from alembic import op
import sqlalchemy as sa

revision = "086"
down_revision = "085"
branch_labels = None
depends_on = None

SCHEMA = "billing"


def upgrade():
    op.add_column(
        "invoices",
        sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    # Los reservados existentes toman su fecha de emisión (la fija Python en UTC).
    op.execute(
        sa.text(
            "UPDATE billing.invoices SET reserved_at = issue_date "
            "WHERE status = 'reserved' AND reserved_at IS NULL"
        )
    )
    op.create_index(
        "ix_billing_invoices_reserved_at",
        "invoices",
        ["reserved_at"],
        schema=SCHEMA,
        postgresql_where=sa.text("status = 'reserved'"),
    )


def downgrade():
    op.drop_index("ix_billing_invoices_reserved_at", table_name="invoices", schema=SCHEMA)
    op.drop_column("invoices", "reserved_at", schema=SCHEMA)
