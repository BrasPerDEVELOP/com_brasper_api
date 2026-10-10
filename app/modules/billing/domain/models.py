# app/modules/billing/domain/models.py
"""Tablas del esquema ``billing``: series, comprobantes y su traza.

- ``series``: correlativo propio por tipo de documento, serie y ambiente. Se
  reserva con ``SELECT ... FOR UPDATE`` para que dos procesos nunca tomen el
  mismo número: SUNAT no permite reutilizar una combinación serie-número.
- ``invoices``: un registro por comprobante emitido (o intentado). Los importes
  se guardan tal cual se enviaron y nunca se recalculan.
- ``invoice_events``: cada intento, respuesta y cambio de estado, para soporte
  y para explicar cualquier hueco de numeración ante una fiscalización.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modules.coin.domain.enums import Currency, CurrencyEnumType
from app.shared.model_base import ORMBaseModel


class BillingSeries(ORMBaseModel):
    __tablename__ = "series"
    __table_args__ = (
        UniqueConstraint("issuer_ruc", "document_type", "series", "environment", name="uq_billing_series"),
        {"schema": "billing"},
    )

    # Cada empresa emisora lleva su propia numeración (la B001 de una no es la de otra).
    issuer_ruc: Mapped[str] = mapped_column(String(11), nullable=False)
    document_type: Mapped[str] = mapped_column(String(2), nullable=False)
    series: Mapped[str] = mapped_column(String(4), nullable=False)
    environment: Mapped[str] = mapped_column(String(20), nullable=False)
    last_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Invoice(ORMBaseModel):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("file_name", name="uq_billing_invoices_file_name"),
        # Una sola boleta/factura viva por operación; las rechazadas o anuladas se conservan.
        Index(
            "uq_billing_invoices_open_transaction",
            "transaction_id",
            unique=True,
            postgresql_where=text("status IN ('reserved', 'sent', 'accepted') AND deleted = false"),
        ),
        {"schema": "billing"},
    )

    transaction_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("transaction.transactions.id"),
        nullable=False,
        index=True,
    )
    # RUC de la empresa emisora (decide el token de APISUNAT y la numeración).
    issuer_ruc: Mapped[str] = mapped_column(String(11), nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(2), nullable=False)  # BillingDocumentType
    series: Mapped[str] = mapped_column(String(4), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    # RUC-TIPO-SERIE-CORRELATIVO, ej. 20608550454-03-B001-00000001
    file_name: Mapped[str] = mapped_column(String(40), nullable=False)
    environment: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[Currency] = mapped_column(CurrencyEnumType, nullable=False)
    taxable_amount: Mapped[float] = mapped_column(Numeric(20, 2), nullable=False)
    igv_amount: Mapped[float] = mapped_column(Numeric(20, 2), nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(20, 2), nullable=False)
    igv_rate: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)

    customer_doc_type: Mapped[str] = mapped_column(String(2), nullable=False)  # catálogo 06 SUNAT
    customer_doc_number: Mapped[str] = mapped_column(String(40), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(250), nullable=False)
    customer_address: Mapped[Optional[str]] = mapped_column(String(250), nullable=True)
    customer_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # InvoiceStatus
    issue_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    apisunat_document_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    sunat_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    xml_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cdr_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pdf_key: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    document_body: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    faults: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    notes: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_polled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # Lo fija Python (UTC) al pasar a `reserved`; el poller detecta así los envíos interrumpidos.
    reserved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    void_reason: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    void_document_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    events: Mapped[list["InvoiceEvent"]] = relationship(
        "InvoiceEvent",
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="InvoiceEvent.created_at",
        lazy="noload",
    )

    @property
    def full_number(self) -> str:
        return f"{self.series}-{self.number:08d}"


class InvoiceEvent(ORMBaseModel):
    __tablename__ = "invoice_events"
    __table_args__ = {"schema": "billing"}

    invoice_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("billing.invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event: Mapped[str] = mapped_column(String(30), nullable=False)  # InvoiceEventType
    payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="events", lazy="noload")
