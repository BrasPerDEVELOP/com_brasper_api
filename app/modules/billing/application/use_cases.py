# app/modules/billing/application/use_cases.py
"""Casos de uso de facturación electrónica: emitir, consultar, reintentar y anular.

Orden de una emisión (ver documento "Integración Brasper · APISUNAT"):

1. Validar la operación (completed, sin comprobante vivo, con comisión > 0).
2. Reservar el correlativo y guardar el comprobante en ``reserved`` CON COMMIT,
   antes de hablar con APISUNAT: ``sendBill`` no es idempotente.
3. Enviar. PENDIENTE → ``sent``; ERROR → ``error`` (el número no se consumió en
   SUNAT, se reutiliza al reintentar); timeout → buscar por serie-número antes
   de dar el envío por perdido.
4. El poller consulta ``getById`` hasta que SUNAT responde: ACEPTADO (se guarda
   el PDF en R2), RECHAZADO (nuevo número al reintentar) o EXCEPCION (mismo número).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from app.core.settings import Settings
from app.modules.billing.application.schemas import (
    BillingStatusDTO,
    InvoiceDTO,
    InvoiceListDTO,
    IssueInvoiceCmd,
    SeriesAlignmentDTO,
    SeriesStatusDTO,
)
from app.modules.billing.application.ubl_builder import (
    CustomerParty,
    InvoiceDraft,
    IssuerParty,
    build_document_body,
    build_file_name,
    issue_moment,
)
from app.modules.billing.domain.amounts import billable_amount, compute_invoice_amounts
from app.modules.billing.domain.enums import (
    SUNAT_IDENTITY_BY_DOCUMENT_TYPE,
    SUNAT_IDENTITY_RUC,
    SUNAT_IDENTITY_SIN_DOCUMENTO,
    BillingDocumentType,
    InvoiceEventType,
    InvoiceStatus,
    SunatDocumentStatus,
)
from app.modules.billing.domain.models import Invoice
from app.modules.billing.interfaces.apisunat_client import (
    ApisunatClientInterface,
    ApisunatError,
    ApisunatTimeout,
    DocumentInfo,
)
from app.modules.billing.interfaces.repository import BillingRepositoryInterface
from app.modules.coin.domain.enums import Currency
from app.modules.transactions.domain.enums import TransactionStatus

logger = logging.getLogger(__name__)

VALID_SUNAT_IDENTITY_CODES = {"0", "1", "4", "6", "7"}


class BillingDisabledError(RuntimeError):
    """El módulo está apagado (``BILLING_ENABLED=False``)."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_enabled(settings: Settings) -> None:
    if not settings.BILLING_ENABLED:
        raise BillingDisabledError("La facturación electrónica está deshabilitada (BILLING_ENABLED=False)")


def issuer_from_settings(settings: Settings) -> IssuerParty:
    return IssuerParty(
        ruc=settings.BILLING_ISSUER_RUC,
        name=settings.BILLING_ISSUER_NAME,
        trade_name=settings.BILLING_ISSUER_TRADE_NAME or settings.BILLING_ISSUER_NAME,
        address=settings.BILLING_ISSUER_ADDRESS,
        ubigeo=settings.BILLING_ISSUER_UBIGEO,
        district=settings.BILLING_ISSUER_DISTRICT,
        province=settings.BILLING_ISSUER_PROVINCE,
        department=settings.BILLING_ISSUER_DEPARTMENT,
    )


def _clean(value: Optional[str]) -> str:
    return " ".join(str(value).split()) if value else ""


def resolve_customer(transaction, user, cmd: Optional[IssueInvoiceCmd]) -> tuple[BillingDocumentType, CustomerParty]:
    """Decide boleta o factura y arma los datos del adquirente.

    El documento del usuario manda; ``cmd`` solo completa o corrige (razón social,
    dirección fiscal, correo). Con RUC → factura y la razón social es obligatoria.
    """
    cmd = cmd or IssueInvoiceCmd()
    raw_type = _clean(cmd.customer_doc_type or getattr(user, "document_type", None)).lower()
    if raw_type in VALID_SUNAT_IDENTITY_CODES:
        sunat_code = raw_type
    else:
        sunat_code = SUNAT_IDENTITY_BY_DOCUMENT_TYPE.get(raw_type, SUNAT_IDENTITY_SIN_DOCUMENTO)

    doc_number = _clean(cmd.customer_doc_number or getattr(user, "document_number", None))
    if sunat_code == SUNAT_IDENTITY_SIN_DOCUMENTO:
        doc_number = doc_number or "-"
    elif not doc_number:
        raise ValueError("El cliente no tiene número de documento registrado")
    if sunat_code == SUNAT_IDENTITY_RUC and not (doc_number.isdigit() and len(doc_number) == 11):
        raise ValueError(f"El RUC del cliente no tiene 11 dígitos: {doc_number}")

    full_name = _clean(f"{getattr(user, 'names', '') or ''} {getattr(user, 'lastnames', '') or ''}")
    name = _clean(cmd.customer_name) or full_name
    if sunat_code == SUNAT_IDENTITY_RUC:
        if not name:
            raise ValueError("Falta la razón social del cliente con RUC")
        document_type = BillingDocumentType.factura
    else:
        if not name:
            name = "CLIENTE"
        document_type = BillingDocumentType.boleta

    customer = CustomerParty(
        doc_type=sunat_code,
        doc_number=doc_number,
        name=name.upper(),
        address=_clean(cmd.customer_address) or None,
        email=_clean(cmd.customer_email or getattr(user, "email", None)) or None,
    )
    return document_type, customer


def _series_for(settings: Settings, document_type: BillingDocumentType) -> str:
    return (
        settings.BILLING_SERIES_FACTURA
        if document_type is BillingDocumentType.factura
        else settings.BILLING_SERIES_BOLETA
    )


def _error_text(payload) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False, default=str)[:2000]
    except (TypeError, ValueError):
        return str(payload)[:2000]


async def _adopt_remote_document(
    repo: BillingRepositoryInterface,
    invoice: Invoice,
    info: DocumentInfo,
    event_payload: dict,
) -> None:
    """El documento ya existe en APISUNAT: se vincula y el poller resuelve su estado final."""
    invoice.status = InvoiceStatus.sent.value
    invoice.apisunat_document_id = info.document_id
    invoice.sunat_status = info.status or SunatDocumentStatus.PENDIENTE.value
    invoice.sent_at = invoice.sent_at or _now()
    invoice.last_error = None
    await repo.add_event(
        invoice.id,
        InvoiceEventType.sent.value,
        {**event_payload, "documentId": info.document_id, "sunat_status": info.status},
    )


async def send_invoice(
    repo: BillingRepositoryInterface,
    client: ApisunatClientInterface,
    settings: Settings,
    invoice: Invoice,
) -> Invoice:
    """Envía (o reenvía) un comprobante ya reservado y persiste el resultado."""
    invoice.attempts = int(invoice.attempts or 0) + 1
    customer_email = invoice.customer_email if settings.BILLING_SEND_CUSTOMER_EMAIL else None
    try:
        result = await client.send_bill(
            file_name=invoice.file_name,
            document_body=invoice.document_body or {},
            customer_email=customer_email,
            reference=str(invoice.transaction_id),
        )
    except ApisunatTimeout as exc:
        recovered: Optional[DocumentInfo] = None
        try:
            recovered = await client.find_by_file_name(invoice.file_name)
        except (ApisunatError, ValueError):
            recovered = None
        if recovered is not None:
            await _adopt_remote_document(repo, invoice, recovered, {"recovered_after_timeout": True})
        else:
            invoice.status = InvoiceStatus.error.value
            invoice.last_error = str(exc)
            await repo.add_event(invoice.id, InvoiceEventType.send_failed.value, {"error": str(exc)})
    except ApisunatError as exc:
        invoice.status = InvoiceStatus.error.value
        invoice.last_error = str(exc)
        await repo.add_event(invoice.id, InvoiceEventType.send_failed.value, {"error": str(exc)})
    else:
        if result.accepted_for_processing:
            invoice.status = InvoiceStatus.sent.value
            invoice.apisunat_document_id = result.document_id
            invoice.sunat_status = SunatDocumentStatus.PENDIENTE.value
            invoice.sent_at = _now()
            invoice.last_error = None
            await repo.add_event(invoice.id, InvoiceEventType.sent.value, {"documentId": result.document_id})
        else:
            invoice.status = InvoiceStatus.error.value
            invoice.last_error = _error_text(result.error or result.raw)
            await repo.add_event(invoice.id, InvoiceEventType.send_failed.value, result.raw)
    await repo.commit()
    await repo.refresh(invoice)
    return invoice


class IssueInvoiceUseCase:
    def __init__(
        self,
        repo: BillingRepositoryInterface,
        client: ApisunatClientInterface,
        settings: Settings,
    ):
        self.repo = repo
        self.client = client
        self.settings = settings

    async def execute(
        self,
        transaction_id: UUID,
        cmd: Optional[IssueInvoiceCmd] = None,
        *,
        actor: Optional[str] = None,
    ) -> InvoiceDTO:
        _ensure_enabled(self.settings)
        transaction = await self.repo.get_transaction_for_billing(transaction_id)
        if transaction is None:
            raise LookupError("Operación no encontrada")
        if transaction.status != TransactionStatus.completed:
            raise ValueError("Solo se emiten comprobantes de operaciones completadas")
        start_date = self.settings.billing_start_date
        reference_date = transaction.payment_date or transaction.created_at
        if start_date and reference_date and reference_date.date() < start_date:
            raise ValueError(
                f"La operación es anterior a la fecha de corte de facturación ({start_date.isoformat()})"
            )
        existing = await self.repo.get_open_invoice(transaction.id)
        if existing is not None:
            raise ValueError(
                f"La operación ya tiene el comprobante {existing.series}-{existing.number:08d} "
                f"en estado {existing.status}"
            )
        amounts = compute_invoice_amounts(
            billable_amount(transaction),
            igv_included=self.settings.BILLING_COMMISSION_INCLUDES_IGV,
            igv_rate=Decimal(str(self.settings.BILLING_IGV_RATE)),
        )
        if amounts is None:
            raise ValueError("La operación no tiene comisión cobrada: no hay nada que facturar")

        tax_rate = await self.repo.get_tax_rate(transaction.tax_rate_id)
        currency = tax_rate.coin_a if tax_rate is not None else Currency.pen
        currency_code = currency.value if hasattr(currency, "value") else str(currency)

        document_type, customer = resolve_customer(transaction, transaction.user, cmd)
        series = _series_for(self.settings, document_type)
        environment = self.settings.APISUNAT_ENVIRONMENT.lower()
        number = await self.repo.reserve_next_number(document_type.value, series, environment)

        issued_at = _now()
        issue_date, issue_time = issue_moment(issued_at)
        draft = InvoiceDraft(
            document_type=document_type,
            series=series,
            number=number,
            issue_date=issue_date,
            issue_time=issue_time,
            currency=currency_code,
            amounts=amounts,
            item_description=self.settings.BILLING_ITEM_DESCRIPTION.format(code=transaction.code),
        )
        body = build_document_body(draft, issuer_from_settings(self.settings), customer)

        invoice = Invoice(
            transaction_id=transaction.id,
            document_type=document_type.value,
            series=series,
            number=number,
            file_name=build_file_name(self.settings.BILLING_ISSUER_RUC, document_type, series, number),
            environment=environment,
            currency=currency,
            taxable_amount=amounts.taxable,
            igv_amount=amounts.igv,
            total_amount=amounts.total,
            igv_rate=amounts.igv_rate,
            customer_doc_type=customer.doc_type,
            customer_doc_number=customer.doc_number,
            customer_name=customer.name,
            customer_address=customer.address,
            customer_email=customer.email,
            status=InvoiceStatus.reserved.value,
            reserved_at=issued_at,
            issue_date=issued_at,
            document_body=body,
            attempts=0,
            created_by=actor,
        )
        await self.repo.add_invoice(invoice)
        await self.repo.flush()
        await self.repo.add_event(
            invoice.id,
            InvoiceEventType.reserved.value,
            {"file_name": invoice.file_name, "actor": actor, "environment": environment},
        )
        await self.repo.set_transaction_billing_date(transaction.id, issued_at)
        # Commit antes de la red: el número queda reservado aunque el envío falle.
        await self.repo.commit()

        await send_invoice(self.repo, self.client, self.settings, invoice)
        return InvoiceDTO.from_entity(invoice)


class PollInvoiceUseCase:
    """Consulta ``getById`` de un comprobante enviado y aplica el estado de SUNAT."""

    def __init__(
        self,
        repo: BillingRepositoryInterface,
        client: ApisunatClientInterface,
        settings: Settings,
        file_service=None,
    ):
        self.repo = repo
        self.client = client
        self.settings = settings
        self.file_service = file_service

    async def execute(self, invoice: Invoice) -> Invoice:
        if invoice.status != InvoiceStatus.sent.value or not invoice.apisunat_document_id:
            return invoice
        try:
            info = await self.client.get_by_id(invoice.apisunat_document_id)
        except ApisunatError as exc:
            invoice.last_polled_at = _now()
            invoice.last_error = str(exc)
            await self.repo.add_event(invoice.id, InvoiceEventType.error.value, {"error": str(exc)})
            await self.repo.commit()
            return invoice

        invoice.last_polled_at = _now()
        invoice.sunat_status = info.status or invoice.sunat_status
        invoice.xml_url = info.xml_url or invoice.xml_url
        invoice.cdr_url = info.cdr_url or invoice.cdr_url
        invoice.faults = info.faults or None
        invoice.notes = info.notes or None

        if info.status == SunatDocumentStatus.ACEPTADO.value:
            invoice.status = InvoiceStatus.accepted.value
            invoice.accepted_at = _now()
            invoice.last_error = None
            await self.repo.add_event(
                invoice.id,
                InvoiceEventType.accepted.value,
                {"xml": info.xml_url, "cdr": info.cdr_url, "notes": info.notes},
            )
            await self._store_pdf(invoice)
        elif info.status == SunatDocumentStatus.RECHAZADO.value:
            invoice.status = InvoiceStatus.rejected.value
            invoice.last_error = _error_text(info.faults) if info.faults else "RECHAZADO por SUNAT"
            await self.repo.add_event(invoice.id, InvoiceEventType.rejected.value, {"faults": info.faults})
        elif info.status == SunatDocumentStatus.EXCEPCION.value:
            invoice.status = InvoiceStatus.exception.value
            invoice.last_error = _error_text(info.faults) if info.faults else "EXCEPCION en SUNAT"
            await self.repo.add_event(invoice.id, InvoiceEventType.exception.value, {"faults": info.faults})
        # PENDIENTE: no se registra evento para no llenar la traza en cada consulta.
        await self.repo.commit()
        return invoice

    async def _store_pdf(self, invoice: Invoice) -> None:
        if self.file_service is None or not invoice.apisunat_document_id:
            return
        try:
            content = await self.client.get_pdf(
                invoice.apisunat_document_id,
                pdf_format=self.settings.BILLING_PDF_FORMAT,
                file_name=invoice.file_name,
            )
            key = f"invoices/{invoice.issue_date.year}/{invoice.file_name}.pdf"
            invoice.pdf_key = await self.file_service.save_raw(key, content)
            await self.repo.add_event(invoice.id, InvoiceEventType.pdf_stored.value, {"key": key})
        except Exception as exc:  # el PDF se puede volver a pedir; no bloquea la aceptación
            logger.warning("No se pudo guardar el PDF de %s: %s", invoice.file_name, exc)


class PollPendingInvoicesUseCase:
    def __init__(self, poll: PollInvoiceUseCase, repo: BillingRepositoryInterface):
        self.poll = poll
        self.repo = repo

    async def execute(self, *, limit: int = 50) -> int:
        pending = await self.repo.list_by_status([InvoiceStatus.sent.value], limit=limit)
        changed = 0
        for invoice in pending:
            before = invoice.status
            await self.poll.execute(invoice)
            if invoice.status != before:
                changed += 1
        return changed


def stale_reserved_after_seconds(settings: Settings) -> float:
    """Tiempo a partir del cual un ``reserved`` se considera envío interrumpido.

    Un envío normal dura como máximo ``sendBill`` + ``getAll`` (dos timeouts); se
    deja un minuto de margen para no "recuperar" un envío que sigue en curso.
    """
    return 2 * float(settings.APISUNAT_TIMEOUT_SECONDS) + 60


class RecoverStaleReservedUseCase:
    """Rescata comprobantes atascados en ``reserved``.

    Pasa cuando el proceso se cae (deploy, reinicio, OOM) entre el commit de la
    reserva y la respuesta de ``sendBill``. Sin esto el comprobante bloquea la
    operación para siempre: cuenta como vivo, no es reintentable y el poller
    solo mira ``sent``. Se busca por serie-número en APISUNAT:

    - existe → se vincula como ``sent`` y el poller resuelve su estado;
    - no existe → ``error`` (el número no se consumió; se reintenta con el mismo);
    - APISUNAT no responde → se deja como está y se intenta en el siguiente ciclo.
    """

    def __init__(
        self,
        repo: BillingRepositoryInterface,
        client: ApisunatClientInterface,
        settings: Settings,
    ):
        self.repo = repo
        self.client = client
        self.settings = settings

    async def execute(self, *, now: Optional[datetime] = None, limit: int = 20) -> int:
        cutoff = (now or _now()) - timedelta(seconds=stale_reserved_after_seconds(self.settings))
        stale = await self.repo.list_stale_reserved(cutoff, limit=limit)
        recovered = 0
        for invoice in stale:
            try:
                remote = await self.client.find_by_file_name(invoice.file_name)
            except (ApisunatError, ValueError) as exc:
                logger.warning("No se pudo verificar el reservado %s: %s", invoice.file_name, exc)
                continue
            if remote is not None:
                await _adopt_remote_document(self.repo, invoice, remote, {"recovered_stale_reserved": True})
            else:
                invoice.status = InvoiceStatus.error.value
                invoice.last_error = "Envío interrumpido antes de llegar a APISUNAT; reintentar"
                await self.repo.add_event(
                    invoice.id, InvoiceEventType.send_failed.value, {"stale_reserved": True}
                )
            await self.repo.commit()
            recovered += 1
        return recovered


class RetryInvoiceUseCase:
    """Reintenta un comprobante en ``exception``/``error`` (mismo número) o ``rejected`` (nuevo número)."""

    def __init__(
        self,
        repo: BillingRepositoryInterface,
        client: ApisunatClientInterface,
        settings: Settings,
    ):
        self.repo = repo
        self.client = client
        self.settings = settings

    async def execute(self, invoice_id: UUID, *, actor: Optional[str] = None) -> InvoiceDTO:
        _ensure_enabled(self.settings)
        invoice = await self.repo.get_invoice(invoice_id)
        if invoice is None:
            raise LookupError("Comprobante no encontrado")
        status = InvoiceStatus(invoice.status)
        if not status.can_retry:
            raise ValueError(f"Un comprobante en estado {invoice.status} no se puede reintentar")
        if invoice.environment != self.settings.APISUNAT_ENVIRONMENT.lower():
            raise ValueError("El comprobante pertenece a otro ambiente de APISUNAT")

        await self.repo.add_event(invoice.id, InvoiceEventType.retry.value, {"actor": actor, "from": invoice.status})
        if status is InvoiceStatus.rejected:
            # El número quedó consumido: se emite uno nuevo con los mismos datos del cliente.
            await self.repo.commit()
            issue = IssueInvoiceUseCase(self.repo, self.client, self.settings)
            cmd = IssueInvoiceCmd(
                customer_name=invoice.customer_name,
                customer_address=invoice.customer_address,
                customer_email=invoice.customer_email,
                customer_doc_type=invoice.customer_doc_type,
                customer_doc_number=invoice.customer_doc_number,
            )
            return await issue.execute(invoice.transaction_id, cmd, actor=actor)
        if status is InvoiceStatus.error:
            # En `error` no se sabe si el envío llegó (p. ej. timeout sin confirmación):
            # antes de reenviar el MISMO número se verifica en APISUNAT. Si no se puede
            # verificar, no se reenvía a ciegas.
            try:
                remote = await self.client.find_by_file_name(invoice.file_name)
            except (ApisunatError, ValueError) as exc:
                await self.repo.commit()
                raise ApisunatError(
                    f"No se pudo verificar en APISUNAT si {invoice.file_name} ya existe; "
                    f"reintenta más tarde: {exc}"
                ) from exc
            if remote is not None:
                await _adopt_remote_document(self.repo, invoice, remote, {"recovered_on_retry": True})
                await self.repo.commit()
                await self.repo.refresh(invoice)
                return InvoiceDTO.from_entity(invoice)
        invoice.status = InvoiceStatus.reserved.value
        invoice.reserved_at = _now()
        await self.repo.commit()
        await send_invoice(self.repo, self.client, self.settings, invoice)
        return InvoiceDTO.from_entity(invoice)


class VoidInvoiceUseCase:
    def __init__(
        self,
        repo: BillingRepositoryInterface,
        client: ApisunatClientInterface,
        settings: Settings,
    ):
        self.repo = repo
        self.client = client
        self.settings = settings

    async def execute(self, invoice_id: UUID, reason: str, *, actor: Optional[str] = None) -> InvoiceDTO:
        _ensure_enabled(self.settings)
        invoice = await self.repo.get_invoice(invoice_id)
        if invoice is None:
            raise LookupError("Comprobante no encontrado")
        if invoice.status != InvoiceStatus.accepted.value or not invoice.apisunat_document_id:
            raise ValueError("Solo se puede anular un comprobante aceptado por SUNAT")
        reason = _clean(reason)
        if not 3 <= len(reason) <= 100:
            raise ValueError("El motivo debe tener entre 3 y 100 caracteres")
        await self.repo.add_event(
            invoice.id, InvoiceEventType.void_requested.value, {"reason": reason, "actor": actor}
        )
        try:
            result = await self.client.void_bill(document_id=invoice.apisunat_document_id, reason=reason)
        except ApisunatError as exc:
            await self.repo.add_event(invoice.id, InvoiceEventType.error.value, {"error": str(exc)})
            await self.repo.commit()
            raise
        if not result.accepted_for_processing:
            await self.repo.add_event(invoice.id, InvoiceEventType.error.value, result.raw)
            await self.repo.commit()
            raise ValueError(f"APISUNAT no aceptó la anulación: {_error_text(result.error or result.raw)}")
        invoice.status = InvoiceStatus.voided.value
        invoice.voided_at = _now()
        invoice.void_reason = reason
        invoice.void_document_id = result.document_id
        await self.repo.add_event(invoice.id, InvoiceEventType.voided.value, {"documentId": result.document_id})
        await self.repo.commit()
        await self.repo.refresh(invoice)
        return InvoiceDTO.from_entity(invoice)


class GetInvoiceUseCase:
    def __init__(self, repo: BillingRepositoryInterface):
        self.repo = repo

    async def execute(self, invoice_id: UUID, *, with_events: bool = True) -> Optional[InvoiceDTO]:
        invoice = await self.repo.get_invoice(invoice_id)
        if invoice is None:
            return None
        events = await self.repo.list_events(invoice.id) if with_events else []
        return InvoiceDTO.from_entity(invoice, events=events)

    async def for_transaction(self, transaction_id: UUID) -> Optional[InvoiceDTO]:
        invoice = await self.repo.get_open_invoice(transaction_id) or await self.repo.get_latest_invoice(
            transaction_id
        )
        if invoice is None:
            return None
        return InvoiceDTO.from_entity(invoice, events=await self.repo.list_events(invoice.id))


class ListInvoicesUseCase:
    def __init__(self, repo: BillingRepositoryInterface):
        self.repo = repo

    async def execute(
        self,
        *,
        status: Optional[str] = None,
        document_type: Optional[str] = None,
        transaction_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> InvoiceListDTO:
        items, total = await self.repo.list_invoices(
            status=status,
            document_type=document_type,
            transaction_id=transaction_id,
            date_from=date_from,
            date_to=date_to,
            skip=skip,
            limit=limit,
        )
        return InvoiceListDTO(
            items=[InvoiceDTO.from_entity(i) for i in items], total=total, skip=skip, limit=limit
        )


class GetInvoicePdfUseCase:
    """PDF desde R2; si aún no está guardado lo pide a APISUNAT y lo almacena."""

    def __init__(
        self,
        repo: BillingRepositoryInterface,
        client: ApisunatClientInterface,
        settings: Settings,
        file_service=None,
    ):
        self.repo = repo
        self.client = client
        self.settings = settings
        self.file_service = file_service

    async def execute(self, invoice_id: UUID) -> tuple[bytes, str]:
        invoice = await self.repo.get_invoice(invoice_id)
        if invoice is None:
            raise LookupError("Comprobante no encontrado")
        if invoice.pdf_key and self.file_service is not None:
            stored = await self.file_service.read_file(invoice.pdf_key)
            if stored:
                return stored[0], f"{invoice.file_name}.pdf"
        if not invoice.apisunat_document_id:
            raise ValueError("El comprobante aún no fue enviado a APISUNAT")
        content = await self.client.get_pdf(
            invoice.apisunat_document_id,
            pdf_format=self.settings.BILLING_PDF_FORMAT,
            file_name=invoice.file_name,
        )
        if self.file_service is not None and invoice.status == InvoiceStatus.accepted.value:
            try:
                key = f"invoices/{invoice.issue_date.year}/{invoice.file_name}.pdf"
                invoice.pdf_key = await self.file_service.save_raw(key, content)
                await self.repo.add_event(invoice.id, InvoiceEventType.pdf_stored.value, {"key": key})
                await self.repo.commit()
            except Exception as exc:
                logger.warning("No se pudo guardar el PDF de %s: %s", invoice.file_name, exc)
        return content, f"{invoice.file_name}.pdf"


class BillingStatusUseCase:
    def __init__(self, repo: BillingRepositoryInterface, settings: Settings):
        self.repo = repo
        self.settings = settings

    async def execute(self) -> BillingStatusDTO:
        s = self.settings
        environment = s.APISUNAT_ENVIRONMENT.lower()
        rows = await self.repo.list_series(environment)
        return BillingStatusDTO(
            enabled=s.BILLING_ENABLED,
            auto_issue=s.BILLING_AUTO_ISSUE,
            environment=environment,
            is_production=s.apisunat_is_production,
            issuer_ruc=s.BILLING_ISSUER_RUC,
            issuer_name=s.BILLING_ISSUER_NAME,
            series_boleta=s.BILLING_SERIES_BOLETA,
            series_factura=s.BILLING_SERIES_FACTURA,
            commission_includes_igv=s.BILLING_COMMISSION_INCLUDES_IGV,
            igv_rate=s.BILLING_IGV_RATE,
            start_date=s.BILLING_START_DATE or None,
            series=[
                SeriesStatusDTO(
                    document_type=r.document_type,
                    series=r.series,
                    environment=r.environment,
                    last_number=int(r.last_number or 0),
                )
                for r in rows
            ],
        )


class AlignSeriesUseCase:
    """Alinea el correlativo local con el último número conocido por APISUNAT.

    Se usa al arrancar en producción o tras emitir fuera de Brasper. Nunca baja
    un correlativo: si el local ya va más adelante, se conserva.
    """

    def __init__(
        self,
        repo: BillingRepositoryInterface,
        client: ApisunatClientInterface,
        settings: Settings,
    ):
        self.repo = repo
        self.client = client
        self.settings = settings

    @staticmethod
    def _extract_last_number(payload: dict) -> Optional[int]:
        for key in ("lastNumber", "last_number", "number", "suggestedNumber"):
            value = payload.get(key)
            if value is None:
                continue
            try:
                number = int(value)
            except (TypeError, ValueError):
                continue
            # suggestedNumber es el SIGUIENTE a usar; los demás son el último usado.
            return number - 1 if key == "suggestedNumber" else number
        return None

    async def execute(self) -> list[SeriesAlignmentDTO]:
        _ensure_enabled(self.settings)
        environment = self.settings.APISUNAT_ENVIRONMENT.lower()
        results: list[SeriesAlignmentDTO] = []
        for document_type in (BillingDocumentType.boleta, BillingDocumentType.factura):
            series = _series_for(self.settings, document_type)
            local = {
                (r.document_type, r.series): int(r.last_number or 0)
                for r in await self.repo.list_series(environment)
            }
            previous = local.get((document_type.value, series), 0)
            payload = await self.client.last_document(document_type=document_type.value, series=series)
            remote = self._extract_last_number(payload if isinstance(payload, dict) else {})
            new_value = max(previous, remote or 0)
            if new_value != previous:
                await self.repo.set_last_number(document_type.value, series, environment, new_value)
            results.append(
                SeriesAlignmentDTO(
                    document_type=document_type.value,
                    series=series,
                    previous_last_number=previous,
                    apisunat_last_number=remote,
                    new_last_number=new_value,
                )
            )
        await self.repo.commit()
        return results
