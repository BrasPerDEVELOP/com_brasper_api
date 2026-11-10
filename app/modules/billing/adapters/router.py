# app/modules/billing/adapters/router.py
"""Rutas de facturación electrónica (boletas y facturas vía APISUNAT)."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from app.core.settings import get_settings
from app.modules.billing.adapters.dependencies import build_apisunat_client

from app.core.routing import LegacyAliasRouter
from app.modules.audit.infrastructure.stage_mutation_audit import stage_mutation_audit
from app.modules.auth.infrastructure.dependencies import get_current_user, require_permission
from app.modules.billing.adapters.dependencies import (
    AlignSeriesUseCaseDep,
    BillingStatusUseCaseDep,
    GetInvoicePdfUseCaseDep,
    GetInvoiceUseCaseDep,
    IssueInvoiceUseCaseDep,
    LatestInvoicesUseCaseDep,
    ListInvoicesUseCaseDep,
    PollInvoiceUseCaseDep,
    PreviewInvoiceUseCaseDep,
    RepoDep,
    RetryInvoiceUseCaseDep,
    RequestInvoiceEmailUseCaseDep,
    VoidInvoiceUseCaseDep,
    require_billing_enabled,
)
from app.modules.billing.application.schemas import (
    BillingStatusDTO,
    InvoiceDTO,
    InvoiceListDTO,
    InvoicePreviewDTO,
    IssueInvoiceCmd,
    SendInvoiceEmailCmd,
    SeriesAlignmentDTO,
    VoidInvoiceCmd,
)
from app.modules.billing.application.use_cases import BillingDisabledError
from app.modules.billing.interfaces.apisunat_client import ApisunatError

router = LegacyAliasRouter(prefix="/billing", tags=["billing"])


@router.get('/credit-notes', dependencies=[Depends(require_permission('billing.view'))])
async def list_credit_notes(issuer_ruc: Optional[str] = Query(None, pattern=r'^\d{11}$')):
    settings = get_settings()
    issuers = [issuer.ruc for issuer in settings.billing_issuers]
    if issuer_ruc and issuer_ruc not in issuers:
        raise HTTPException(status_code=422, detail='Empresa emisora no configurada')
    provider = build_apisunat_client(settings)
    notes = []
    for ruc in ([issuer_ruc] if issuer_ruc else issuers):
        try:
            for item in await provider.for_issuer(ruc).list_credit_notes():
                notes.append({
                    'id': str(item.get('id') or item.get('_id') or item.get('documentId') or ''),
                    'file_name': item.get('fileName'), 'issuer_ruc': ruc,
                    'status': item.get('status'), 'issue_time': item.get('issueTime'),
                    'xml_url': item.get('xml'), 'cdr_url': item.get('cdr'),
                    'production': item.get('production'),
                })
        except Exception as exc:
            raise HTTPException(status_code=502, detail='No se pudieron consultar las notas de crédito de APISUNAT') from exc
    return sorted(notes, key=lambda note: note['issue_time'] or 0, reverse=True)


@router.get('/credit-notes/{issuer_ruc}/{document_id}/pdf', dependencies=[Depends(require_permission('billing.view'))])
async def get_credit_note_pdf(issuer_ruc: str, document_id: str):
    settings = get_settings()
    if issuer_ruc not in [issuer.ruc for issuer in settings.billing_issuers] or not document_id.isalnum():
        raise HTTPException(status_code=422, detail='Nota de crédito inválida')
    client = build_apisunat_client(settings).for_issuer(issuer_ruc)
    try:
        info = await client.get_by_id(document_id)
        if not info.file_name or not info.file_name.startswith(f'{issuer_ruc}-07-'):
            raise HTTPException(status_code=404, detail='Nota de crédito no encontrada')
        content = await client.get_pdf(document_id, pdf_format='A4', file_name=info.file_name)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail='No se pudo descargar el PDF de APISUNAT') from exc
    return Response(content=content, media_type='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="{info.file_name}.pdf"'
    })


@router.get('/invoices/export-month', dependencies=[Depends(require_permission('billing.view'))])
async def export_invoices_month(
    repo: RepoDep,
    pdf_use_case: GetInvoicePdfUseCaseDep,
    month: str = Query(..., pattern=r'^\d{4}-(0[1-9]|1[0-2])$'),
    issuer_ruc: Optional[str] = Query(None, pattern=r'^\d{11}$'),
):
    from app.modules.billing.application.monthly_export import export_month
    year, month_number = map(int, month.split('-'))
    try:
        content = await export_month(repo, pdf_use_case, year, month_number, issuer_ruc)
    except (ValueError, LookupError) as exc:
        _raise_for(exc)
    return Response(content=content, media_type='application/zip', headers={
        'Content-Disposition': f'attachment; filename="comprobantes-sunat-{month}.zip"'
    })


def _actor_label(actor: dict) -> Optional[str]:
    return str(actor.get("email") or actor.get("user_id") or "") or None


def _raise_for(exc: Exception) -> None:
    if isinstance(exc, LookupError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, BillingDisabledError):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    if isinstance(exc, ApisunatError):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"APISUNAT: {exc}")
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    raise exc


@router.get(
    "/status",
    response_model=BillingStatusDTO,
    dependencies=[Depends(require_permission("billing.view"))],
)
async def billing_status(use_case: BillingStatusUseCaseDep):
    """Configuración vigente (ambiente, series, correlativos). No requiere BILLING_ENABLED."""
    return await use_case.execute()


@router.get(
    "/invoices",
    response_model=InvoiceListDTO,
    dependencies=[Depends(require_permission("billing.view"))],
)
async def list_invoices(
    use_case: ListInvoicesUseCaseDep,
    status_filter: Optional[str] = Query(None, alias="status"),
    document_type: Optional[str] = Query(None, pattern=r"^(01|03|07)$"),
    transaction_id: Optional[UUID] = Query(None),
    issuer_ruc: Optional[str] = Query(None, pattern=r"^\d{11}$"),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    page: Optional[int] = Query(None, ge=1),
    page_size: Optional[int] = Query(None, ge=1, le=200),
):
    if page is not None or page_size is not None:
        limit = page_size or 10
        skip = ((page or 1) - 1) * limit
    return await use_case.execute(
        status=status_filter,
        document_type=document_type,
        transaction_id=transaction_id,
        issuer_ruc=issuer_ruc,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/invoices/by-transactions",
    response_model=list[InvoiceDTO],
    dependencies=[Depends(require_permission("billing.view"))],
)
async def latest_invoices_for_transactions(
    use_case: LatestInvoicesUseCaseDep,
    transaction_ids: list[UUID] = Query(..., min_length=1, max_length=100),
):
    """Último comprobante de cada operación (para pintar una página del backoffice en una consulta)."""
    return await use_case.execute(transaction_ids)


@router.get(
    "/transactions/{transaction_id}/preview",
    response_model=InvoicePreviewDTO,
    dependencies=[Depends(require_permission("billing.view"))],
)
async def preview_transaction_invoice(
    transaction_id: UUID,
    use_case: PreviewInvoiceUseCaseDep,
    customer_name: Optional[str] = Query(None, max_length=250),
    customer_address: Optional[str] = Query(None, max_length=250),
    customer_email: Optional[str] = Query(None, max_length=255),
    customer_doc_type: Optional[str] = Query(None, max_length=20),
    customer_doc_number: Optional[str] = Query(None, max_length=40),
    document_type: Optional[str] = Query(None, pattern=r"^(01|03)$"),
    issuer_ruc: Optional[str] = Query(None, pattern=r"^\d{11}$"),
    send_customer_email: bool = Query(False),
):
    """Boleta o factura que saldría, con adquirente e importes. No reserva número ni llama a APISUNAT."""
    cmd = IssueInvoiceCmd(
        customer_name=customer_name,
        customer_address=customer_address,
        customer_email=customer_email,
        customer_doc_type=customer_doc_type,
        customer_doc_number=customer_doc_number,
        document_type=document_type,
        issuer_ruc=issuer_ruc,
        send_customer_email=send_customer_email,
    )
    try:
        return await use_case.execute(transaction_id, cmd)
    except Exception as exc:  # noqa: BLE001
        _raise_for(exc)


@router.get(
    "/invoices/{invoice_id}",
    response_model=InvoiceDTO,
    dependencies=[Depends(require_permission("billing.view"))],
)
async def get_invoice(invoice_id: UUID, use_case: GetInvoiceUseCaseDep):
    dto = await use_case.execute(invoice_id)
    if dto is None:
        raise HTTPException(status_code=404, detail="Comprobante no encontrado")
    return dto


@router.get(
    "/invoices/{invoice_id}/pdf",
    dependencies=[Depends(require_permission("billing.view"))],
    response_class=Response,
)
async def get_invoice_pdf(invoice_id: UUID, use_case: GetInvoicePdfUseCaseDep):
    try:
        content, filename = await use_case.execute(invoice_id)
    except Exception as exc:  # noqa: BLE001 - se traduce a HTTP
        _raise_for(exc)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get(
    "/transactions/{transaction_id}/invoice",
    response_model=InvoiceDTO,
    dependencies=[Depends(require_permission("billing.view"))],
)
async def get_transaction_invoice(transaction_id: UUID, use_case: GetInvoiceUseCaseDep):
    """Comprobante vivo de la operación o, si no hay, el último intento."""
    dto = await use_case.for_transaction(transaction_id)
    if dto is None:
        raise HTTPException(status_code=404, detail="La operación no tiene comprobante")
    return dto


@router.post(
    "/transactions/{transaction_id}/issue",
    response_model=InvoiceDTO,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("billing.issue")), Depends(require_billing_enabled)],
)
async def issue_invoice(
    transaction_id: UUID,
    use_case: IssueInvoiceUseCaseDep,
    cmd: Optional[IssueInvoiceCmd] = None,
    actor=Depends(get_current_user),
    audit_event=Depends(stage_mutation_audit("billing.invoices.issue", "invoice")),
):
    """Emite la boleta o factura de una operación completada."""
    try:
        dto = await use_case.execute(transaction_id, cmd, actor=_actor_label(actor))
    except Exception as exc:  # noqa: BLE001
        _raise_for(exc)
    if audit_event:
        audit_event.entity_id = str(dto.id)
        audit_event.new_values = {
            "transaction_id": str(transaction_id),
            "file_name": dto.file_name,
            "status": dto.status,
            "total_amount": dto.total_amount,
        }
    return dto


@router.post(
    "/invoices/{invoice_id}/retry",
    response_model=InvoiceDTO,
    dependencies=[Depends(require_permission("billing.issue")), Depends(require_billing_enabled)],
)
async def retry_invoice(
    invoice_id: UUID,
    use_case: RetryInvoiceUseCaseDep,
    actor=Depends(get_current_user),
    audit_event=Depends(stage_mutation_audit("billing.invoices.retry", "invoice")),
):
    try:
        dto = await use_case.execute(invoice_id, actor=_actor_label(actor))
    except Exception as exc:  # noqa: BLE001
        _raise_for(exc)
    if audit_event:
        audit_event.entity_id = str(invoice_id)
        audit_event.new_values = {"result_invoice_id": str(dto.id), "status": dto.status}
    return dto


@router.post(
    "/invoices/{invoice_id}/email",
    response_model=InvoiceDTO,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_permission("billing.issue")), Depends(require_billing_enabled)],
)
async def request_invoice_email(
    invoice_id: UUID,
    cmd: SendInvoiceEmailCmd,
    use_case: RequestInvoiceEmailUseCaseDep,
    actor=Depends(get_current_user),
    audit_event=Depends(stage_mutation_audit("billing.invoices.email", "invoice")),
):
    try:
        dto = await use_case.execute(invoice_id, cmd, actor=_actor_label(actor))
    except Exception as exc:
        _raise_for(exc)
    if audit_event:
        audit_event.entity_id = str(invoice_id)
        audit_event.new_values = {"email_status": dto.email_status}
    return dto


@router.post(
    "/invoices/{invoice_id}/refresh",
    response_model=InvoiceDTO,
    dependencies=[Depends(require_permission("billing.view")), Depends(require_billing_enabled)],
)
async def refresh_invoice(
    invoice_id: UUID,
    use_case: PollInvoiceUseCaseDep,
    repo: RepoDep,
    audit_event=Depends(stage_mutation_audit("billing.invoices.refresh", "invoice")),
):
    """Consulta el estado en APISUNAT ahora mismo, sin esperar al poller."""
    invoice = await repo.get_invoice(invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Comprobante no encontrado")
    previous_status = invoice.status
    invoice = await use_case.execute(invoice)
    if audit_event:
        audit_event.entity_id = str(invoice_id)
        audit_event.old_values = {"status": previous_status}
        audit_event.new_values = {"status": invoice.status, "sunat_status": invoice.sunat_status}
    return InvoiceDTO.from_entity(invoice, events=await repo.list_events(invoice.id))


@router.post(
    "/invoices/{invoice_id}/void",
    response_model=InvoiceDTO,
    dependencies=[Depends(require_permission("billing.void")), Depends(require_billing_enabled)],
)
async def void_invoice(
    invoice_id: UUID,
    cmd: VoidInvoiceCmd,
    use_case: VoidInvoiceUseCaseDep,
    actor=Depends(get_current_user),
    audit_event=Depends(stage_mutation_audit("billing.invoices.void", "invoice")),
):
    try:
        dto = await use_case.execute(invoice_id, cmd.reason, actor=_actor_label(actor))
    except Exception as exc:  # noqa: BLE001
        _raise_for(exc)
    if audit_event:
        audit_event.entity_id = str(invoice_id)
        audit_event.new_values = {"reason": cmd.reason, "status": dto.status}
    return dto


@router.post(
    "/series/align",
    response_model=list[SeriesAlignmentDTO],
    dependencies=[Depends(require_permission("billing.issue")), Depends(require_billing_enabled)],
)
async def align_series(
    use_case: AlignSeriesUseCaseDep,
    audit_event=Depends(stage_mutation_audit("billing.series.align", "billing_series")),
):
    """Alinea los correlativos locales con el último número que conoce APISUNAT."""
    try:
        result = await use_case.execute()
    except Exception as exc:  # noqa: BLE001
        _raise_for(exc)
    if audit_event:
        audit_event.new_values = [r.model_dump() for r in result]
    return result


__all__ = ["router"]
