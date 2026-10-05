"""Esquema billing: series, comprobantes electrónicos (APISUNAT) y su traza; permisos."""
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "085"
down_revision = "084"
branch_labels = None
depends_on = None

SCHEMA = "billing"
PERMISSIONS = ("billing.view", "billing.issue")


def _base_columns():
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(250), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("(now() AT TIME ZONE 'America/Lima')"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("(now() AT TIME ZONE 'America/Lima')"),
        ),
    ]


def upgrade():
    op.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))

    op.create_table(
        "series",
        *_base_columns(),
        sa.Column("document_type", sa.String(2), nullable=False),
        sa.Column("series", sa.String(4), nullable=False),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("document_type", "series", "environment", name="uq_billing_series"),
        schema=SCHEMA,
    )

    op.create_table(
        "invoices",
        *_base_columns(),
        sa.Column(
            "transaction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("transaction.transactions.id"),
            nullable=False,
        ),
        sa.Column("document_type", sa.String(2), nullable=False),
        sa.Column("series", sa.String(4), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(40), nullable=False),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column(
            "currency",
            postgresql.ENUM("PEN", "BRL", "USD", name="currency", schema="coin", create_type=False),
            nullable=False,
        ),
        sa.Column("taxable_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("igv_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("igv_rate", sa.Numeric(6, 4), nullable=False),
        sa.Column("customer_doc_type", sa.String(2), nullable=False),
        sa.Column("customer_doc_number", sa.String(40), nullable=False),
        sa.Column("customer_name", sa.String(250), nullable=False),
        sa.Column("customer_address", sa.String(250), nullable=True),
        sa.Column("customer_email", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("issue_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("apisunat_document_id", sa.String(64), nullable=True),
        sa.Column("sunat_status", sa.String(20), nullable=True),
        sa.Column("xml_url", sa.Text(), nullable=True),
        sa.Column("cdr_url", sa.Text(), nullable=True),
        sa.Column("pdf_key", sa.String(300), nullable=True),
        sa.Column("document_body", postgresql.JSONB(), nullable=True),
        sa.Column("faults", postgresql.JSONB(), nullable=True),
        sa.Column("notes", postgresql.JSONB(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("void_reason", sa.String(100), nullable=True),
        sa.Column("void_document_id", sa.String(64), nullable=True),
        sa.UniqueConstraint("file_name", name="uq_billing_invoices_file_name"),
        schema=SCHEMA,
    )
    op.create_index("ix_billing_invoices_transaction_id", "invoices", ["transaction_id"], schema=SCHEMA)
    op.create_index("ix_billing_invoices_status", "invoices", ["status"], schema=SCHEMA)
    op.create_index(
        "ix_billing_invoices_apisunat_document_id", "invoices", ["apisunat_document_id"], schema=SCHEMA
    )
    # Una sola boleta/factura viva por operación (las rechazadas o anuladas se conservan).
    op.create_index(
        "uq_billing_invoices_open_transaction",
        "invoices",
        ["transaction_id"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("status IN ('reserved', 'sent', 'accepted') AND deleted = false"),
    )

    op.create_table(
        "invoice_events",
        *_base_columns(),
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event", sa.String(30), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        schema=SCHEMA,
    )
    op.create_index("ix_billing_invoice_events_invoice_id", "invoice_events", ["invoice_id"], schema=SCHEMA)

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE "user".role_permission
            SET permissions = COALESCE(permissions, '[]'::jsonb) || CAST(:perms AS jsonb)
            WHERE role = 'accounting'
            """
        ),
        {"perms": json.dumps(list(PERMISSIONS))},
    )
    conn.execute(
        sa.text(
            """
            UPDATE "user".role_permission
            SET permissions = (
                SELECT COALESCE(jsonb_agg(DISTINCT value), '[]'::jsonb)
                FROM jsonb_array_elements(permissions)
            )
            WHERE role = 'accounting'
            """
        )
    )


def downgrade():
    conn = op.get_bind()
    for permission in PERMISSIONS:
        conn.execute(
            sa.text('UPDATE "user".role_permission SET permissions = permissions - :perm'),
            {"perm": permission},
        )
    op.drop_table("invoice_events", schema=SCHEMA)
    op.drop_table("invoices", schema=SCHEMA)
    op.drop_table("series", schema=SCHEMA)
