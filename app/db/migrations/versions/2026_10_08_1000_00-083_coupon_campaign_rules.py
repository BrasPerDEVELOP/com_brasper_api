"""Reglas de campañas sobre el ledger de cupones existente.

El índice 052 limitaba TODOS los cupones a una redención por usuario, incluso
cuando per_user_limit era mayor. Se conserva la serialización por fila del cupón.
Downgrade requiere resolver redenciones múltiples antes de reponer dicho índice.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "083"
down_revision = "082"
branch_labels = None
depends_on = None


def upgrade():
    # Primero y tolerante: las migraciones corren en AUTOCOMMIT (sentencia a sentencia);
    # si el índice ya no existía, fallar al final dejaba columnas creadas con la versión en 082.
    op.execute("DROP INDEX IF EXISTS world_cup.uq_coupon_redemptions_coupon_user_live")
    op.add_column("coupons", sa.Column("campaign_rules", postgresql.JSONB(), nullable=True), schema="transaction")
    op.add_column("coupons", sa.Column("campaign_version", sa.Integer(), nullable=False, server_default="1"), schema="transaction")
    op.add_column("coupons", sa.Column("published_version", sa.Integer(), nullable=True), schema="transaction")
    op.add_column("transactions", sa.Column("coupon_campaign_version", sa.Integer(), nullable=True), schema="transaction")
    op.create_table("coupon_campaign_versions",
                    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
                    sa.Column("coupon_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("transaction.coupons.id"), nullable=False),
                    sa.Column("version", sa.Integer(), nullable=False),
                    sa.Column("payload", postgresql.JSONB(), nullable=False),
                    sa.Column("deleted", sa.Boolean(), nullable=False, server_default="false"),
                    sa.Column("enable", sa.Boolean(), nullable=False, server_default="true"),
                    sa.Column("created_by", sa.String(250)),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
                    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
                    sa.UniqueConstraint("coupon_id", "version", name="uq_campaign_version"), schema="transaction")


def downgrade():
    # No se eliminan canjes para forzar el downgrade: el UNIQUE fallará si hay
    # datos incompatibles, permitiendo restaurar el backup/versión anterior.
    op.create_index("uq_coupon_redemptions_coupon_user_live", "coupon_redemptions",
                    ["coupon_id", "user_id"], unique=True, schema="world_cup",
                    postgresql_where=sa.text("deleted = false"))
    op.drop_column("coupons", "campaign_version", schema="transaction")
    op.drop_column("coupons", "campaign_rules", schema="transaction")
    op.drop_column("coupons", "published_version", schema="transaction")
    op.drop_column("transactions", "coupon_campaign_version", schema="transaction")
    op.drop_table("coupon_campaign_versions", schema="transaction")
