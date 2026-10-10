"""Plantilla JSON UBL para APISUNAT y leyenda del importe en letras."""
from datetime import date, time
from decimal import Decimal

import pytest

from app.modules.billing.application.ubl_builder import (
    CustomerParty,
    InvoiceDraft,
    IssuerParty,
    amount_in_words,
    build_document_body,
    build_file_name,
    number_to_words_es,
)
from app.modules.billing.domain.amounts import compute_invoice_amounts
from app.modules.billing.domain.enums import BillingDocumentType

ISSUER = IssuerParty(
    ruc="20608550454",
    name="BRASPER 21 S.A.C.",
    trade_name="brasper transferencias",
    address="AV. AREQUIPA NRO. 2447 INT. 409",
    ubigeo="150116",
    district="LINCE",
    province="LIMA",
    department="LIMA",
)


def _draft(document_type, series, total="40.00", currency="PEN"):
    return InvoiceDraft(
        document_type=document_type,
        series=series,
        number=12,
        issue_date=date(2026, 10, 3),
        issue_time=time(10, 5, 0),
        currency=currency,
        amounts=compute_invoice_amounts(Decimal(total)),
        item_description="Comisión por servicio de transferencia, operación PEN-BRL-000123",
    )


@pytest.mark.parametrize(
    "number, words",
    [
        (0, "CERO"),
        (7, "SIETE"),
        (16, "DIECISÉIS"),
        (21, "VEINTIUNO"),
        (30, "TREINTA"),
        (45, "CUARENTA Y CINCO"),
        (100, "CIEN"),
        (101, "CIENTO UNO"),
        (515, "QUINIENTOS QUINCE"),
        (1000, "MIL"),
        (1001, "MIL UNO"),
        (21000, "VEINTIUN MIL"),
        (123456, "CIENTO VEINTITRES MIL CUATROCIENTOS CINCUENTA Y SEIS"),
        (1_000_000, "UN MILLÓN"),
        (2_500_000, "DOS MILLONES QUINIENTOS MIL"),
    ],
)
def test_numeros_en_letras(number, words):
    assert number_to_words_es(number) == words


def test_leyenda_importe_en_letras():
    assert amount_in_words(Decimal("40.00"), "PEN") == "CUARENTA CON 00/100 SOLES"
    assert amount_in_words(Decimal("1250.75"), "USD") == "MIL DOSCIENTOS CINCUENTA CON 75/100 DÓLARES AMERICANOS"


def test_file_name_sigue_el_formato_sunat():
    assert build_file_name("20608550454", BillingDocumentType.boleta, "B001", 1) == "20608550454-03-B001-00000001"
    assert build_file_name("20608550454", BillingDocumentType.factura, "F001", 345) == "20608550454-01-F001-00000345"


def test_boleta_a_persona_con_dni():
    customer = CustomerParty(doc_type="1", doc_number="45678912", name="MARIA PEREZ", email="m@x.pe")
    body = build_document_body(_draft(BillingDocumentType.boleta, "B001"), ISSUER, customer)

    assert body["cbc:ID"]["_text"] == "B001-00000012"
    assert body["cbc:InvoiceTypeCode"] == {"_attributes": {"listID": "0101"}, "_text": "03"}
    assert body["cbc:IssueDate"]["_text"] == "2026-10-03"
    assert body["cbc:DocumentCurrencyCode"]["_text"] == "PEN"
    assert body["cbc:Note"][0]["_text"] == "CUARENTA CON 00/100 SOLES"

    supplier = body["cac:AccountingSupplierParty"]["cac:Party"]
    assert supplier["cac:PartyIdentification"]["cbc:ID"] == {"_attributes": {"schemeID": "6"}, "_text": "20608550454"}
    assert supplier["cac:PartyLegalEntity"]["cbc:RegistrationName"]["_text"] == "BRASPER 21 S.A.C."
    assert supplier["cac:PartyLegalEntity"]["cac:RegistrationAddress"]["cbc:ID"]["_text"] == "150116"

    buyer = body["cac:AccountingCustomerParty"]["cac:Party"]
    assert buyer["cac:PartyIdentification"]["cbc:ID"] == {"_attributes": {"schemeID": "1"}, "_text": "45678912"}
    assert buyer["cac:PartyLegalEntity"]["cbc:RegistrationName"]["_text"] == "MARIA PEREZ"

    assert body["cac:TaxTotal"]["cbc:TaxAmount"] == {"_attributes": {"currencyID": "PEN"}, "_text": "6.10"}
    totals = body["cac:LegalMonetaryTotal"]
    assert totals["cbc:LineExtensionAmount"]["_text"] == "33.90"
    assert totals["cbc:TaxInclusiveAmount"]["_text"] == "40.00"
    assert totals["cbc:PayableAmount"]["_text"] == "40.00"

    line = body["cac:InvoiceLine"][0]
    assert line["cbc:InvoicedQuantity"] == {"_attributes": {"unitCode": "ZZ"}, "_text": "1"}
    assert line["cbc:LineExtensionAmount"]["_text"] == "33.90"
    assert line["cac:PricingReference"]["cac:AlternativeConditionPrice"]["cbc:PriceAmount"]["_text"] == "40.00"
    assert line["cac:PricingReference"]["cac:AlternativeConditionPrice"]["cbc:PriceTypeCode"]["_text"] == "01"
    subtotal = line["cac:TaxTotal"]["cac:TaxSubtotal"][0]
    assert subtotal["cac:TaxCategory"]["cbc:Percent"]["_text"] == "18"
    assert subtotal["cac:TaxCategory"]["cbc:TaxExemptionReasonCode"]["_text"] == "10"
    assert subtotal["cac:TaxCategory"]["cac:TaxScheme"]["cbc:ID"]["_text"] == "1000"
    assert line["cac:Price"]["cbc:PriceAmount"]["_text"] == "33.90"
    assert "operación PEN-BRL-000123" in line["cac:Item"]["cbc:Description"]["_text"]
    assert body["cac:PaymentTerms"][0]["cbc:PaymentMeansID"]["_text"] == "Contado"


def test_factura_a_empresa_con_ruc_y_direccion():
    customer = CustomerParty(doc_type="6", doc_number="20123456789", name="ACME S.A.C.", address="JR. LIMA 123")
    body = build_document_body(_draft(BillingDocumentType.factura, "F001", total="118.00", currency="USD"), ISSUER, customer)
    assert body["cbc:InvoiceTypeCode"]["_text"] == "01"
    assert body["cbc:ID"]["_text"] == "F001-00000012"
    buyer = body["cac:AccountingCustomerParty"]["cac:Party"]
    assert buyer["cac:PartyIdentification"]["cbc:ID"]["_attributes"]["schemeID"] == "6"
    assert buyer["cac:PartyLegalEntity"]["cac:RegistrationAddress"]["cac:AddressLine"]["cbc:Line"]["_text"] == "JR. LIMA 123"
    assert body["cac:LegalMonetaryTotal"]["cbc:LineExtensionAmount"] == {"_attributes": {"currencyID": "USD"}, "_text": "100.00"}
    assert body["cbc:Note"][0]["_text"].endswith("DÓLARES AMERICANOS")


def test_factura_exige_ruc_y_boleta_admite_cliente_con_ruc():
    with pytest.raises(ValueError):
        build_document_body(
            _draft(BillingDocumentType.factura, "F001"),
            ISSUER,
            CustomerParty(doc_type="1", doc_number="45678912", name="MARIA PEREZ"),
        )
    # Boleta a quien tiene RUC: válida si el cliente la pide (no usará crédito fiscal).
    body = build_document_body(
        _draft(BillingDocumentType.boleta, "B001"),
        ISSUER,
        CustomerParty(doc_type="6", doc_number="20123456789", name="ACME"),
    )
    assert body["cbc:InvoiceTypeCode"]["_text"] == "03"
