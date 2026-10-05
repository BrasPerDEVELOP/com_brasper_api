# app/modules/billing/interfaces/apisunat_client.py
"""Puerto hacia APISUNAT (https://docs.apisunat.com)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


class ApisunatError(Exception):
    """Fallo de red o respuesta inesperada de APISUNAT (no un rechazo de SUNAT)."""


class ApisunatTimeout(ApisunatError):
    """La petición no obtuvo respuesta: no se sabe si el documento llegó."""


@dataclass(frozen=True)
class SendBillResult:
    status: str  # PENDIENTE | ERROR
    document_id: Optional[str] = None
    error: Optional[dict] = None
    raw: dict = field(default_factory=dict)

    @property
    def accepted_for_processing(self) -> bool:
        return self.status == "PENDIENTE" and bool(self.document_id)


@dataclass(frozen=True)
class DocumentInfo:
    document_id: str
    status: str  # PENDIENTE | ACEPTADO | RECHAZADO | EXCEPCION
    file_name: Optional[str] = None
    xml_url: Optional[str] = None
    cdr_url: Optional[str] = None
    faults: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    production: Optional[bool] = None
    raw: dict = field(default_factory=dict)


class ApisunatClientInterface(ABC):
    @abstractmethod
    async def send_bill(
        self,
        *,
        file_name: str,
        document_body: dict[str, Any],
        customer_email: Optional[str] = None,
        reference: Optional[str] = None,
    ) -> SendBillResult: ...

    @abstractmethod
    async def get_by_id(self, document_id: str) -> DocumentInfo: ...

    @abstractmethod
    async def find_by_file_name(self, file_name: str) -> Optional[DocumentInfo]:
        """Busca por serie-número; útil tras un timeout de ``send_bill``."""
        ...

    @abstractmethod
    async def get_pdf(self, document_id: str, *, pdf_format: str, file_name: str) -> bytes: ...

    @abstractmethod
    async def void_bill(self, *, document_id: str, reason: str) -> SendBillResult: ...

    @abstractmethod
    async def last_document(self, *, document_type: str, series: str) -> dict[str, Any]:
        """Último número usado en APISUNAT para alinear el correlativo al arrancar."""
        ...
