from datetime import date, time
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from PIL import Image
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from app.modules.billing.application.ubl_builder import CustomerParty, InvoiceDraft, IssuerParty, build_document_body
from app.modules.billing.application.use_cases import GetInvoicePdfUseCase
from app.modules.billing.domain.amounts import compute_invoice_amounts
from app.modules.billing.domain.enums import BillingDocumentType
from app.modules.billing.infrastructure.branded_pdf import render_boleta, _verification, LOGO


def source_pdf(number='BB02-00000002'):
    output = BytesIO()
    pdf = canvas.Canvas(output)
    pdf.drawString(40, 780, number)
    pdf.drawString(40, 750, 'T852MVs8b0fBMSBezzGUGhT3W2Q=')
    # Monochrome stand-in: assertions compare the original image pixels, not a rebuilt QR.
    qr = Image.new('RGB', (100, 100), 'white')
    for x in range(100):
        for y in range(100):
            if (x // 7 + y // 7) % 2:
                qr.putpixel((x, y), (0, 0, 0))
    pdf.drawImage(ImageReader(qr), 40, 600, 100, 100)
    pdf.save()
    return output.getvalue()


def invoice(ruc='20611936428', name='INGENITECH S.A.C.', doc_type='4', doc_number='001234567'):
    amounts = compute_invoice_amounts(Decimal('59.86'))
    issuer = IssuerParty(ruc=ruc, name=name, trade_name='Brasper', address='Av. Ejemplo 100',
                         ubigeo='150116', district='LINCE', province='LIMA', department='LIMA')
    customer = CustomerParty(doc_type=doc_type, doc_number=doc_number, name='Cliente de prueba', address='Av. Cliente 123')
    draft = InvoiceDraft(document_type=BillingDocumentType.boleta, series='BB02', number=2,
                         issue_date=date(2026, 11, 3), issue_time=time(9, 11, 12), currency='PEN',
                         amounts=amounts, item_description=f'Comisión por transferencia. Razón social: {name}')
    return SimpleNamespace(id=uuid4(), transaction_id=uuid4(), issuer_ruc=ruc,
        full_number=draft.full_number, file_name=f'{ruc}-03-{draft.full_number}', document_type='03',
        currency='PEN', taxable_amount=amounts.taxable, igv_amount=amounts.igv,
        total_amount=amounts.total, igv_rate=Decimal('.18'), status='accepted', environment='production',
        customer_doc_type=doc_type, customer_doc_number=doc_number, customer_name=customer.name,
        customer_address=customer.address, document_body=build_document_body(draft, issuer, customer),
        pdf_key='original.pdf', apisunat_document_id='provider-id')


@pytest.mark.parametrize('ruc,name', [('20611936428', 'INGENITECH S.A.C.'), ('20608550454', 'BRASPER 21 S.A.C.')])
@pytest.mark.parametrize('code,label,number', [('1', 'DNI', '12345678'), ('4', 'Carné de extranjería', '001234567'), ('7', 'Pasaporte', 'AB123456')])
def test_branded_boleta_preserves_fiscal_data_and_verification(ruc, name, code, label, number):
    source = source_pdf()
    result = render_boleta(invoice(ruc, name, code, number), source)
    reader = PdfReader(BytesIO(result))
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    for expected in (ruc, name, label, number, '59.86', '50.73', '9.13', 'BB02-00000002'):
        assert expected in text
    original_qr, original_hash = _verification(source, 'BB02-00000002')
    actual_qr, actual_hash = _verification(result, 'BB02-00000002')
    assert original_hash == actual_hash
    assert Image.open(BytesIO(original_qr)).tobytes() == Image.open(BytesIO(actual_qr)).tobytes()
    with Image.open(LOGO) as logo:
        assert any(item.image.size == logo.size for item in reader.pages[0].images)


def test_missing_fiscal_document_is_not_replaced_with_current_profile():
    result = render_boleta(invoice(doc_type='0', doc_number='-'), source_pdf(),
                           profile_document_type='cpf', profile_document_number='12345678901')
    text = PdfReader(BytesIO(result)).pages[0].extract_text()
    assert 'Sin documento tributario' in text
    assert 'Número: -' in text
    assert 'referencial' in text
    assert 'CPF 12345678901' in text


def test_mismatched_source_is_rejected():
    with pytest.raises(ValueError, match='no corresponde'):
        render_boleta(invoice(), source_pdf('BB02-00000099'))


@pytest.mark.asyncio
async def test_download_renders_cached_original_without_replacing_it():
    record = invoice()
    repo = SimpleNamespace(get_invoice=AsyncMock(return_value=record),
                           get_transaction_for_billing=AsyncMock(return_value=None))
    storage = SimpleNamespace(read_file=AsyncMock(return_value=(source_pdf(), 'application/pdf')),
                              save_raw=AsyncMock())
    client = SimpleNamespace(get_pdf=AsyncMock())
    result, filename = await GetInvoicePdfUseCase(repo, client, None, storage).execute(record.id)
    assert 'Carné de extranjería' in PdfReader(BytesIO(result)).pages[0].extract_text()
    assert filename == record.file_name + '.pdf'
    storage.save_raw.assert_not_awaited()
    client.get_pdf.assert_not_awaited()
