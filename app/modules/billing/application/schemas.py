# app/modules/billing/application/schemas.py
"""Contratos HTTP del módulo de facturación (snake_case, como el resto del backoffice)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.settings import get_settings
from app.modules.billing.domain.enums import BillingDocumentType


class InvoiceEventDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event: str
    payload: Optional[Any] = None
    created_at: Optional[datetime] = None


class InvoiceDTO(BaseModel):
    id: UUID
    transaction_id: UUID
    issuer_ruc: str
    issuer_name: str
    document_type: str
    document_type_label: str
    series: str
    number: int
    full_number: str
    file_name: str
    environment: str
    currency: str
    taxable_amount: float
    igv_amount: float
    total_amount: float
    igv_rate: float
    customer_doc_type: str
    customer_doc_number: str
    customer_name: str
    customer_address: Optional[str] = None
    customer_email: Optional[str] = None
    status: str
    issue_date: datetime
    apisunat_document_id: Optional[str] = None
    sunat_status: Optional[str] = None
    xml_url: Optional[str] = None
    cdr_url: Optional[str] = None
    has_pdf: bool = False
    faults: Optional[Any] = None
    notes: Optional[Any] = None
    last_error: Optional[str] = None
    attempts: int = 0
    last_polled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    voided_at: Optional[datetime] = None
    void_reason: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    events: list[InvoiceEventDTO] = Field(default_factory=list)

    @classmethod
    def from_entity(cls, entity, *, events: Optional[list] = None) -> "InvoiceDTO":
        try:
            label = BillingDocumentType(entity.document_type).label
        except ValueError:
            label = entity.document_type
        currency = entity.currency.value if hasattr(entity.currency, "value") else str(entity.currency)
        issuer_ruc = getattr(entity, "issuer_ruc", None) or str(entity.file_name).split("-")[0]
        issuer = get_settings().billing_issuer(issuer_ruc)
        return cls(
            id=entity.id,
            transaction_id=entity.transaction_id,
            issuer_ruc=issuer_ruc,
            issuer_name=issuer.display_name if issuer else issuer_ruc,
            document_type=entity.document_type,
            document_type_label=label,
            series=entity.series,
            number=entity.number,
            full_number=f"{entity.series}-{entity.number:08d}",
            file_name=entity.file_name,
            environment=entity.environment,
            currency=currency,
            taxable_amount=float(entity.taxable_amount),
            igv_amount=float(entity.igv_amount),
            total_amount=float(entity.total_amount),
            igv_rate=float(entity.igv_rate),
            customer_doc_type=entity.customer_doc_type,
            customer_doc_number=entity.customer_doc_number,
            customer_name=entity.customer_name,
            customer_address=entity.customer_address,
            customer_email=entity.customer_email,
            status=entity.status,
            issue_date=entity.issue_date,
            apisunat_document_id=entity.apisunat_document_id,
            sunat_status=entity.sunat_status,
            xml_url=entity.xml_url,
            cdr_url=entity.cdr_url,
            has_pdf=bool(entity.pdf_key),
            faults=entity.faults,
            notes=entity.notes,
            last_error=entity.last_error,
            attempts=int(entity.attempts or 0),
            last_polled_at=entity.last_polled_at,
            sent_at=entity.sent_at,
            accepted_at=entity.accepted_at,
            voided_at=entity.voided_at,
            void_reason=entity.void_reason,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            events=[InvoiceEventDTO.model_validate(e) for e in (events or [])],
        )


class InvoiceListDTO(BaseModel):
    items: list[InvoiceDTO]
    total: int
    skip: int
    limit: int


class IssueInvoiceCmd(BaseModel):
    """Datos opcionales del adquirente que completan o corrigen los del usuario.

    ``customer_doc_type`` acepta el valor de ``DocumentType`` (dni, ruc, ce, …)
    o directamente el código SUNAT del catálogo 06 (0, 1, 4, 6, 7).
    """

    customer_name: Optional[str] = Field(default=None, max_length=250)
    customer_address: Optional[str] = Field(default=None, max_length=250)
    customer_email: Optional[str] = Field(default=None, max_length=255)
    customer_doc_type: Optional[str] = Field(default=None, max_length=20)
    customer_doc_number: Optional[str] = Field(default=None, max_length=40)
    #: "01" factura o "03" boleta. Vacío = automático según el documento del cliente.
    document_type: Optional[Literal["01", "03"]] = None
    #: RUC de la empresa emisora. Vacío = la empresa por defecto.
    issuer_ruc: Optional[str] = Field(default=None, pattern=r"^\d{11}$")


class InvoicePreviewDTO(BaseModel):
    """Comprobante que saldría al emitir (sin reservar número). ``can_issue`` + ``reason`` explican si se puede."""

    transaction_id: UUID
    can_issue: bool
    reason: Optional[str] = None
    enabled: bool
    environment: str
    issuer_ruc: Optional[str] = None
    issuer_name: Optional[str] = None
    document_type: Optional[str] = None
    document_type_label: Optional[str] = None
    series: Optional[str] = None
    currency: Optional[str] = None
    taxable_amount: Optional[float] = None
    igv_amount: Optional[float] = None
    total_amount: Optional[float] = None
    igv_rate: Optional[float] = None
    customer_doc_type: Optional[str] = None
    customer_doc_number: Optional[str] = None
    customer_name: Optional[str] = None
    customer_address: Optional[str] = None
    customer_email: Optional[str] = None
    item_description: Optional[str] = None


class LatestInvoicesQuery(BaseModel):
    transaction_ids: list[UUID] = Field(min_length=1, max_length=200)


class VoidInvoiceCmd(BaseModel):
    reason: str = Field(min_length=3, max_length=100)


class SeriesStatusDTO(BaseModel):
    issuer_ruc: str
    document_type: str
    series: str
    environment: str
    last_number: int


class BillingIssuerDTO(BaseModel):
    """Empresa emisora visible en el backoffice (sin credenciales)."""

    ruc: str
    name: str
    trade_name: Optional[str] = None
    is_default: bool = False
    #: Tiene personaId y token de APISUNAT cargados.
    configured: bool = False


class BillingStatusDTO(BaseModel):
    enabled: bool
    auto_issue: bool
    environment: str
    is_production: bool
    issuer_ruc: str
    issuer_name: str
    series_boleta: str
    series_factura: str
    commission_includes_igv: bool
    igv_rate: float
    start_date: Optional[str] = None
    default_issuer_ruc: Optional[str] = None
    issuers: list[BillingIssuerDTO] = Field(default_factory=list)
    series: list[SeriesStatusDTO] = Field(default_factory=list)


class SeriesAlignmentDTO(BaseModel):
    issuer_ruc: str
    document_type: str
    series: str
    previous_last_number: int
    apisunat_last_number: Optional[int] = None
    new_last_number: int
