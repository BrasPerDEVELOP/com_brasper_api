"""Descarga mensual de los comprobantes APISUNAT y sus archivos originales."""
from datetime import datetime, timezone, timedelta
from io import BytesIO
from urllib.parse import urlparse
from zipfile import ZipFile, ZIP_DEFLATED

import httpx

from app.modules.billing.application.use_cases import GetInvoicePdfUseCase


async def export_month(repo, pdf_use_case: GetInvoicePdfUseCase, year: int, month: int, issuer_ruc=None):
    start = datetime(year, month, 1, tzinfo=timezone(timedelta(hours=-5)))
    end = datetime(year + (month == 12), month % 12 + 1, 1,
                   tzinfo=timezone(timedelta(hours=-5)))
    invoices, total = await repo.list_invoices(
        issuer_ruc=issuer_ruc, date_from=start, date_to=end, skip=0, limit=1000,
    )
    if total > 1000:
        raise ValueError('Hay más de 1000 comprobantes; selecciona una empresa para reducir la descarga')
    if not invoices:
        raise LookupError('No hay comprobantes en ese mes')

    output = BytesIO()
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
        with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
            missing = []
            for invoice in invoices:
                folder = f'{invoice.issuer_ruc}/{invoice.file_name}/'
                if invoice.status not in ('accepted', 'voided'):
                    missing.append(f'{invoice.file_name}: comprobante no aceptado')
                    continue
                try:
                    pdf, _ = await pdf_use_case.execute(invoice.id)
                    archive.writestr(folder + invoice.file_name + '.pdf', pdf)
                except (ValueError, LookupError, httpx.HTTPError) as exc:
                    missing.append(f'{invoice.file_name}: PDF no disponible ({type(exc).__name__})')
                for kind, url in (('XML', invoice.xml_url), ('CDR', invoice.cdr_url)):
                    parsed = urlparse(url or '')
                    if parsed.scheme != 'https' or parsed.hostname != 'cdn.apisunat.com':
                        missing.append(f'{invoice.file_name}: {kind} no disponible')
                        continue
                    try:
                        response = await client.get(url)
                        response.raise_for_status()
                        if len(response.content) > 20_000_000 or not response.content:
                            raise ValueError('Archivo vacío o demasiado grande')
                        extension = '.zip' if response.content.startswith(b'PK\x03\x04') else '.xml'
                        archive.writestr(folder + invoice.file_name + '-' + kind + extension, response.content)
                    except (httpx.HTTPError, ValueError):
                        missing.append(f'{invoice.file_name}: {kind} no disponible')
            if missing:
                archive.writestr('archivos_no_disponibles.txt', '\n'.join(missing) + '\n')
    return output.getvalue()
