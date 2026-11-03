"""Representación Brasper de boletas; conserva el QR y hash del PDF de APISUNAT."""
from io import BytesIO
from pathlib import Path
import re
from xml.sax.saxutils import escape

from PIL import Image as PillowImage
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, KeepTogether

LOGO = Path(__file__).resolve().parents[1] / 'assets' / 'brasper-logo.png'
INDIGO = colors.HexColor('#454BD1')
CYAN = colors.HexColor('#10B9DB')
INK = colors.HexColor('#17243B')
MUTED = colors.HexColor('#617089')
PALE = colors.HexColor('#F0F4FF')
DOC_TYPES = {'0': 'Sin documento tributario', '1': 'DNI', '4': 'Carné de extranjería',
             '6': 'RUC', '7': 'Pasaporte', 'A': 'Cédula diplomática'}
PROFILE_TYPES = {'dni': 'DNI', 'ce': 'Carné de extranjería', 'ruc': 'RUC',
                 'cpf': 'CPF', 'cnpj': 'CNPJ', 'passport': 'Pasaporte', 'other': 'Otro documento'}


def _text(value):
    return str(value.get('_text', '')) if isinstance(value, dict) else str(value or '')


def _verification(source: bytes, full_number: str):
    reader = PdfReader(BytesIO(source))
    text = '\n'.join(page.extract_text() or '' for page in reader.pages)
    if full_number not in text:
        raise ValueError('El PDF original no corresponde al comprobante')
    hashes = re.findall(r'(?m)^\s*([A-Za-z0-9+/]{27}=)\s*$', text)
    qr = []
    for page in reader.pages:
        for item in page.images:
            im = item.image.convert('RGB')
            if im.width != im.height or im.width < 60:
                continue
            palette = im.getcolors(im.width * im.height) or []
            # El QR del proveedor es una imagen cuadrada monocroma; se copia sin reconstruirlo.
            if palette and all(max(rgb) - min(rgb) < 5 for _, rgb in palette):
                buf = BytesIO()
                im.save(buf, format='PNG')
                qr.append(buf.getvalue())
    if len(qr) != 1 or len(set(hashes)) != 1:
        raise ValueError('No se pudo conservar el QR y hash del comprobante original')
    return qr[0], hashes[0]


def render_boleta(invoice, source: bytes, *, profile_document_type=None, profile_document_number=None) -> bytes:
    """Datos tributarios del snapshot UBL; ficha actual solo como referencia explícita."""
    qr, digest = _verification(source, invoice.full_number)
    body = invoice.document_body or {}
    supplier = body.get('cac:AccountingSupplierParty', {}).get('cac:Party', {})
    legal = supplier.get('cac:PartyLegalEntity', {})
    issuer_name = _text(legal.get('cbc:RegistrationName')) or invoice.issuer_ruc
    address = _text(legal.get('cac:RegistrationAddress', {}).get('cac:AddressLine', {}).get('cbc:Line'))
    currency = getattr(invoice.currency, 'value', invoice.currency).upper()
    symbols = {'PEN': 'S/', 'USD': 'US$', 'BRL': 'R$'}
    symbol = symbols.get(currency, currency)
    width = A4[0] - 72
    styles = {
        'body': ParagraphStyle('body', fontName='Helvetica', fontSize=10, leading=15, textColor=INK),
        'small': ParagraphStyle('small', fontName='Helvetica', fontSize=8, leading=12, textColor=MUTED),
        'title': ParagraphStyle('title', fontName='Helvetica-Bold', fontSize=14, leading=19, textColor=INK),
        'white': ParagraphStyle('white', fontName='Helvetica-Bold', fontSize=10, leading=14, textColor=colors.white),
        'right': ParagraphStyle('right', fontName='Helvetica', fontSize=10, leading=15, textColor=INK, alignment=TA_RIGHT),
    }
    def p(value, style='body'):
        return Paragraph(escape(str(value or '')).replace('\n', '<br/>'), styles[style])
    def table(rows, widths, *, background=None):
        result = Table(rows, colWidths=widths, hAlign='LEFT')
        commands = [('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 12),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 12), ('TOPPADDING', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 9)]
        if background: commands.append(('BACKGROUND', (0, 0), (-1, -1), background))
        result.setStyle(TableStyle(commands))
        return result

    output = BytesIO()
    pdf = SimpleDocTemplate(output, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=30, bottomMargin=42,
                            title=f'Boleta {invoice.full_number}', author='Brasper Transferencias')
    with PillowImage.open(LOGO) as logo_source:
        logo_height = 205 * logo_source.height / logo_source.width
    logo = Image(str(LOGO), width=205, height=logo_height, mask='auto')
    number_box = table([[p('BOLETA DE VENTA ELECTRÓNICA', 'white')],
                        [p(f'RUC {invoice.issuer_ruc}', 'white')],
                        [p(invoice.full_number, 'white')]], [230], background=INDIGO)
    number_box.setStyle(TableStyle([('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    header = table([[logo, number_box]], [width - 230, 230])
    header.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
    story = [header, Spacer(1, 12), p(issuer_name, 'title'), p(address, 'small'), Spacer(1, 16)]
    date = _text(body.get('cbc:IssueDate'))
    time = _text(body.get('cbc:IssueTime'))
    state = 'ANULADO' if invoice.status == 'voided' else 'ACEPTADO POR SUNAT'
    if invoice.environment != 'production': state = 'PRUEBA - SIN VALIDEZ TRIBUTARIA'
    story += [table([[p(f'EMISIÓN (LIMA)\n{date} {time}', 'small'), p(f'MONEDA\n{currency}', 'small'), p(state, 'small')]],
                    [width * .44, width * .20, width * .36], background=PALE), Spacer(1, 18)]
    doc_label = DOC_TYPES.get(invoice.customer_doc_type, f'Tipo SUNAT {invoice.customer_doc_type}')
    number = invoice.customer_doc_number or '-'
    raw_type = getattr(profile_document_type, 'value', profile_document_type)
    if invoice.customer_doc_type == '0' and number != '-' and str(profile_document_number or '') == number:
        doc_label = PROFILE_TYPES.get(raw_type, doc_label)
    customer = [[p('CLIENTE', 'small')], [p(invoice.customer_name, 'title')],
                [p(f'Tipo de documento: {doc_label}    |    Número: {number}')]]
    if invoice.customer_address: customer.append([p(f'Dirección: {invoice.customer_address}', 'small')])
    if number == '-' and profile_document_number:
        customer.append([p(f'Documento registrado en la ficha (referencial): {PROFILE_TYPES.get(raw_type, "Documento")} {profile_document_number}', 'small')])
    story += [table(customer, [width], background=PALE), Spacer(1, 20)]
    lines = body.get('cac:InvoiceLine') or []
    rows = [[p('CANT.', 'white'), p('DESCRIPCIÓN', 'white'), p('P. UNITARIO', 'white'), p('IMPORTE', 'white')]]
    for line in lines:
        description = _text(line.get('cac:Item', {}).get('cbc:Description'))
        qty = _text(line.get('cbc:InvoicedQuantity')) or '1'
        # La boleta de comisión tiene una línea: total incluye IGV, igual al PDF original.
        if len(lines) != 1:
            raise ValueError('La plantilla de boleta requiere una sola comisión')
        amount = f'{invoice.total_amount:,.2f}'
        rows.append([p(qty), p(description), p(amount, 'right'), p(amount, 'right')])
    if not lines: raise ValueError('El comprobante no tiene detalle UBL')
    items = table(rows, [60, width - 225, 85, 80])
    items.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),INDIGO),('LINEBELOW',(0,-1),(-1,-1),.7,CYAN)]))
    story += [items, Spacer(1, 15)]
    totals = table([
        [p('Operación gravada'), p(f'{symbol} {invoice.taxable_amount:,.2f}', 'right')],
        [p(f'IGV {float(invoice.igv_rate) * 100:g}%'), p(f'{symbol} {invoice.igv_amount:,.2f}', 'right')],
        [p('IMPORTE TOTAL', 'white'), p(f'{symbol} {invoice.total_amount:,.2f}', 'white')],
    ], [width - 125, 125])
    totals.setStyle(TableStyle([('BACKGROUND',(0,-1),(-1,-1),INDIGO)]))
    notes = body.get('cbc:Note') or []
    if isinstance(notes, dict): notes = [notes]
    words = next((_text(n) for n in notes if n.get('_attributes', {}).get('languageLocaleID') == '1000'), '')
    story += [KeepTogether([totals, Spacer(1, 10), p(f'SON: {words}', 'small')]), Spacer(1, 22)]
    verification = table([[Image(BytesIO(qr), width=85, height=85),
        [p('VERIFICACIÓN DEL COMPROBANTE', 'small'), p(digest, 'small'), Spacer(1,6),
         p('Representación impresa de la boleta de venta electrónica. Consulta su validez en apisunat.com/buscar.', 'small')]]], [109, width-109])
    story.append(KeepTogether([verification]))
    def footer(canvas, document):
        canvas.setStrokeColor(CYAN)
        canvas.setLineWidth(2)
        canvas.line(36, 29, A4[0]-36, 29)
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(36, 16, 'Brasper Transferencias')
        canvas.drawRightString(A4[0]-36, 16, f'{invoice.full_number}  |  Página {document.page}')
    pdf.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
