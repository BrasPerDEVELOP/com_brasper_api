# app/modules/billing/domain/enums.py
"""Enumeraciones del módulo de facturación electrónica (SUNAT vía APISUNAT)."""
from __future__ import annotations

import enum


class BillingDocumentType(str, enum.Enum):
    """Código SUNAT del tipo de comprobante (catálogo 01)."""

    factura = "01"
    boleta = "03"
    nota_credito = "07"

    @property
    def series_prefix(self) -> str:
        return "F" if self is BillingDocumentType.factura else "B"

    @property
    def label(self) -> str:
        return {
            BillingDocumentType.factura: "Factura",
            BillingDocumentType.boleta: "Boleta de venta",
            BillingDocumentType.nota_credito: "Nota de crédito",
        }[self]


class InvoiceStatus(str, enum.Enum):
    """Ciclo de vida de un comprobante dentro de Brasper.

    reserved → sent → accepted | rejected | exception; además voided y error.
    """

    reserved = "reserved"  # número tomado y JSON armado; aún no se envió
    sent = "sent"  # APISUNAT respondió PENDIENTE; esperando a SUNAT
    accepted = "accepted"  # ACEPTADO por SUNAT (puede traer observaciones en notes)
    rejected = "rejected"  # RECHAZADO: sin validez y el número queda consumido
    exception = "exception"  # EXCEPCION: sin validez y el número NO se consume
    error = "error"  # APISUNAT devolvió status ERROR al enviar; número no consumido
    voided = "voided"  # dado de baja (comunicación de baja / reversión)

    @property
    def is_open(self) -> bool:
        """True si el comprobante sigue vivo para la operación (bloquea emitir otro)."""
        return self in (InvoiceStatus.reserved, InvoiceStatus.sent, InvoiceStatus.accepted)

    @property
    def can_retry(self) -> bool:
        return self in (InvoiceStatus.exception, InvoiceStatus.error, InvoiceStatus.rejected)


OPEN_INVOICE_STATUSES: tuple[str, ...] = tuple(s.value for s in InvoiceStatus if s.is_open)


class SunatDocumentStatus(str, enum.Enum):
    """Estados que devuelve APISUNAT en sendBill / getById."""

    PENDIENTE = "PENDIENTE"
    ACEPTADO = "ACEPTADO"
    RECHAZADO = "RECHAZADO"
    EXCEPCION = "EXCEPCION"
    ERROR = "ERROR"


# Catálogo 06 de SUNAT: tipo de documento de identidad del adquirente.
SUNAT_IDENTITY_SIN_DOCUMENTO = "0"
SUNAT_IDENTITY_DNI = "1"
SUNAT_IDENTITY_CE = "4"
SUNAT_IDENTITY_RUC = "6"
SUNAT_IDENTITY_PASAPORTE = "7"

# Mapa desde ``users.domain.enums.DocumentType`` (valores en minúscula).
SUNAT_IDENTITY_BY_DOCUMENT_TYPE: dict[str, str] = {
    "dni": SUNAT_IDENTITY_DNI,
    "ce": SUNAT_IDENTITY_CE,
    "ruc": SUNAT_IDENTITY_RUC,
    "passport": SUNAT_IDENTITY_PASAPORTE,
    "cpf": SUNAT_IDENTITY_SIN_DOCUMENTO,
    "cnpj": SUNAT_IDENTITY_SIN_DOCUMENTO,
    "other": SUNAT_IDENTITY_SIN_DOCUMENTO,
}


class InvoiceEventType(str, enum.Enum):
    reserved = "reserved"
    sent = "sent"
    send_failed = "send_failed"
    polled = "polled"
    accepted = "accepted"
    rejected = "rejected"
    exception = "exception"
    pdf_stored = "pdf_stored"
    void_requested = "void_requested"
    voided = "voided"
    retry = "retry"
    error = "error"
