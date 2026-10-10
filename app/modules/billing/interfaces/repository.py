# app/modules/billing/interfaces/repository.py
"""Puerto de persistencia del módulo de facturación."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Sequence
from uuid import UUID

from app.modules.billing.domain.models import BillingSeries, Invoice, InvoiceEvent


class BillingRepositoryInterface(ABC):
    # --- Datos de la operación ---------------------------------------------
    @abstractmethod
    async def get_transaction_for_billing(self, transaction_id: UUID):
        """Transacción con su usuario cargado, o ``None``."""
        ...

    @abstractmethod
    async def get_tax_rate(self, tax_rate_id: UUID):
        ...

    @abstractmethod
    async def set_transaction_billing_date(self, transaction_id: UUID, value: datetime) -> None: ...

    # --- Series ----------------------------------------------------------------
    @abstractmethod
    async def reserve_next_number(self, document_type: str, series: str, environment: str) -> int:
        """Incrementa y devuelve el correlativo bajo bloqueo de fila."""
        ...

    @abstractmethod
    async def list_series(self, environment: str) -> list[BillingSeries]: ...

    @abstractmethod
    async def set_last_number(
        self, document_type: str, series: str, environment: str, last_number: int
    ) -> BillingSeries: ...

    # --- Comprobantes ------------------------------------------------------------
    @abstractmethod
    async def get_invoice(self, invoice_id: UUID) -> Optional[Invoice]: ...

    @abstractmethod
    async def get_open_invoice(self, transaction_id: UUID) -> Optional[Invoice]: ...

    @abstractmethod
    async def get_latest_invoice(self, transaction_id: UUID) -> Optional[Invoice]: ...

    @abstractmethod
    async def list_invoices(
        self,
        *,
        status: Optional[str] = None,
        document_type: Optional[str] = None,
        transaction_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Invoice], int]: ...

    @abstractmethod
    async def list_by_status(self, statuses: Sequence[str], *, limit: int = 50) -> list[Invoice]: ...

    @abstractmethod
    async def latest_invoices_for_transactions(self, transaction_ids: Sequence[UUID]) -> list[Invoice]:
        """El comprobante más reciente de cada operación (las que no tienen, no aparecen)."""
        ...

    @abstractmethod
    async def list_stale_reserved(self, reserved_before: datetime, *, limit: int = 50) -> list[Invoice]:
        """Comprobantes en ``reserved`` desde antes de ``reserved_before`` (envío interrumpido)."""
        ...

    @abstractmethod
    async def list_events(self, invoice_id: UUID) -> list[InvoiceEvent]: ...

    @abstractmethod
    async def add_invoice(self, entity: Invoice) -> Invoice: ...

    @abstractmethod
    async def add_event(self, invoice_id: UUID, event: str, payload: Optional[dict] = None) -> InvoiceEvent: ...

    @abstractmethod
    async def flush(self) -> None: ...

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def refresh(self, entity) -> None: ...
