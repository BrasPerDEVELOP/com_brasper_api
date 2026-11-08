from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID
from sqlalchemy import DateTime, ForeignKey, Numeric, String, BigInteger
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.shared.model_base import ORMBase


class OmieInvoice(ORMBase):
    __tablename__ = "omie_invoices"
    __table_args__ = {"schema": "billing"}
    transaction_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("transaction.transactions.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    os_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    nfse_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    nfse_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
