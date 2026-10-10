"""billing: varias empresas emisoras (RUC por comprobante y por correlativo).

Cada empresa (p. ej. BRASPER 21 e INGENITECH) tiene su propio token de APISUNAT
y su propia numeración: la B001 de una no es la B001 de la otra. Por eso:

- ``billing.series`` agrega ``issuer_ruc`` y el UNIQUE pasa a ser
  (issuer_ruc, document_type, series, environment). Se conserva el nombre
  ``uq_billing_series`` porque el repositorio lo usa en ``ON CONFLICT``.
- ``billing.invoices`` agrega ``issuer_ruc``. Los existentes lo toman del propio
  ``file_name`` (RRRRRRRRRRR-TT-SSSS-CCCCCCCC), que siempre empieza por el RUC.

Revision ID: 087
Revises: 086
"""
from alembic import op
import sqlalchemy as sa

revision = "087"
down_revision = "086"
branch_labels = None
depends_on = None

SCHEMA = "billing"
LEGACY_RUC = "20608550454"  # emisor único hasta esta migración (BILLING_ISSUER_RUC por defecto)


def upgrade():
    op.add_column("invoices", sa.Column("issuer_ruc", sa.String(11), nullable=True), schema=SCHEMA)
    op.execute(
        sa.text("UPDATE billing.invoices SET issuer_ruc = split_part(file_name, '-', 1) WHERE issuer_ruc IS NULL")
    )
    op.alter_column("invoices", "issuer_ruc", nullable=False, schema=SCHEMA)
    op.create_index("ix_billing_invoices_issuer_ruc", "invoices", ["issuer_ruc"], schema=SCHEMA)

    op.add_column("series", sa.Column("issuer_ruc", sa.String(11), nullable=True), schema=SCHEMA)
    op.execute(
        sa.text(
            """
            UPDATE billing.series AS s
            SET issuer_ruc = COALESCE(
                (
                    SELECT i.issuer_ruc FROM billing.invoices AS i
                    WHERE i.document_type = s.document_type
                      AND i.series = s.series
                      AND i.environment = s.environment
                    ORDER BY i.number DESC
                    LIMIT 1
                ),
                :legacy
            )
            WHERE s.issuer_ruc IS NULL
            """
        ).bindparams(legacy=LEGACY_RUC)
    )
    op.alter_column("series", "issuer_ruc", nullable=False, schema=SCHEMA)
    op.drop_constraint("uq_billing_series", "series", schema=SCHEMA, type_="unique")
    op.create_unique_constraint(
        "uq_billing_series",
        "series",
        ["issuer_ruc", "document_type", "series", "environment"],
        schema=SCHEMA,
    )


def downgrade():
    op.drop_constraint("uq_billing_series", "series", schema=SCHEMA, type_="unique")
    op.create_unique_constraint(
        "uq_billing_series", "series", ["document_type", "series", "environment"], schema=SCHEMA
    )
    op.drop_column("series", "issuer_ruc", schema=SCHEMA)
    op.drop_index("ix_billing_invoices_issuer_ruc", table_name="invoices", schema=SCHEMA)
    op.drop_column("invoices", "issuer_ruc", schema=SCHEMA)
