"""Esquema finance: tasas mensuales a soles, categorías y egresos; permisos."""
import json
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "082"
down_revision = "081"
branch_labels = None
depends_on = None

SCHEMA = "finance"
CATEGORIES = (
    "Planilla",
    "Viáticos",
    "Legal",
    "Capacitación",
    "Publicidad",
    "Salud",
    "Alimento",
    "Servicios",
    "Ropa",
    "Impuestos",
    "Otros",
)
PERMISSIONS = (
    "fx_rates.view",
    "fx_rates.update",
    "expenses.view",
    "expenses.create",
    "expenses.update",
    "expenses.delete",
)


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
        "fx_month_rates",
        *_base_columns(),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column(
            "currency",
            postgresql.ENUM("PEN", "BRL", "USD", name="currency", schema="coin", create_type=False),
            nullable=False,
        ),
        sa.Column("rate_to_pen", sa.Numeric(20, 8), nullable=False),
        sa.UniqueConstraint("year", "month", "currency", name="uq_fx_month_rate"),
        schema=SCHEMA,
    )
    op.create_index("ix_finance_fx_month_rates_year", "fx_month_rates", ["year"], schema=SCHEMA)

    op.create_table(
        "expense_categories",
        *_base_columns(),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        schema=SCHEMA,
    )
    op.create_index("ix_finance_expense_categories_name", "expense_categories", ["name"], schema=SCHEMA)

    op.create_table(
        "expenses",
        *_base_columns(),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.expense_categories.id"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("amount_pen", sa.Numeric(20, 2), nullable=False),
        schema=SCHEMA,
    )
    op.create_index("ix_finance_expenses_expense_date", "expenses", ["expense_date"], schema=SCHEMA)
    op.create_index("ix_finance_expenses_category_id", "expenses", ["category_id"], schema=SCHEMA)

    conn = op.get_bind()
    for position, name in enumerate(CATEGORIES):
        conn.execute(
            sa.text(
                f'INSERT INTO "{SCHEMA}".expense_categories (id, name, position, deleted, enable) '
                "VALUES (:id, :name, :position, false, true)"
            ),
            {"id": str(uuid.uuid4()), "name": name, "position": position},
        )

    conn.execute(
        sa.text(
            """
            UPDATE "user".role_permission
            SET permissions = COALESCE(permissions, '[]'::jsonb) || CAST(:perms AS jsonb)
            WHERE role = 'accounting'
            """
        ),
        {"perms": json.dumps([p for p in PERMISSIONS])},
    )
    # Quita duplicados si alguno ya existía.
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
    op.drop_table("expenses", schema=SCHEMA)
    op.drop_table("expense_categories", schema=SCHEMA)
    op.drop_table("fx_month_rates", schema=SCHEMA)
