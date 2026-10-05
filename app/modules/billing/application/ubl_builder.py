# app/modules/billing/application/ubl_builder.py
"""Arma el ``documentBody`` (JSON con estructura UBL 2.1) que recibe APISUNAT.

APISUNAT convierte este JSON al XML firmado: cada elemento es un objeto con
``_text`` y, cuando aplica, ``_attributes``. La plantilla cubre el caso de
Brasper: un solo ítem (la comisión del servicio) gravado con IGV, venta interna,
pago al contado. Antes de emitir en producción debe cotejarse con el
generador JSON del portal de APISUNAT (Configuración de Empresa → botón ``{ }``).

Catálogos SUNAT usados:
- 01 tipo de comprobante (01 factura, 03 boleta); listID 0101 = venta interna.
- 06 tipo de documento de identidad del adquirente (0, 1, 4, 6, 7).
- 07 afectación del IGV: 10 = gravado, operación onerosa.
- 05 tributo: 1000 = IGV, código internacional VAT.
- 16 tipo de precio: 01 = precio unitario (incluye IGV).
- 52 leyenda 1000 = importe en letras.
- Unidad ZZ = servicio.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Optional

from app.modules.billing.domain.amounts import InvoiceAmounts
from app.modules.billing.domain.enums import BillingDocumentType, SUNAT_IDENTITY_RUC

CURRENCY_WORDS = {"PEN": "SOLES", "USD": "DÓLARES AMERICANOS", "BRL": "REALES"}


@dataclass(frozen=True)
class IssuerParty:
    ruc: str
    name: str
    trade_name: str
    address: str
    ubigeo: str
    district: str
    province: str
    department: str


@dataclass(frozen=True)
class CustomerParty:
    doc_type: str  # catálogo 06
    doc_number: str
    name: str
    address: Optional[str] = None
    email: Optional[str] = None


@dataclass(frozen=True)
class InvoiceDraft:
    document_type: BillingDocumentType
    series: str
    number: int
    issue_date: date
    issue_time: time
    currency: str
    amounts: InvoiceAmounts
    item_description: str

    @property
    def full_number(self) -> str:
        return f"{self.series}-{self.number:08d}"


def build_file_name(ruc: str, document_type: BillingDocumentType, series: str, number: int) -> str:
    """RRRRRRRRRRR-TT-SSSS-CCCCCCCC, ej. 20608550454-03-B001-00000001."""
    return f"{ruc}-{document_type.value}-{series}-{number:08d}"


# --- Importe en letras -------------------------------------------------------
_UNITS = ["", "UNO", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE"]
_TEENS = [
    "DIEZ", "ONCE", "DOCE", "TRECE", "CATORCE", "QUINCE",
    "DIECISÉIS", "DIECISIETE", "DIECIOCHO", "DIECINUEVE",
]
_TENS = ["", "", "VEINTE", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA", "SETENTA", "OCHENTA", "NOVENTA"]
_HUNDREDS = [
    "", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS",
    "QUINIENTOS", "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS",
]


def _below_thousand(n: int) -> str:
    if n == 0:
        return ""
    if n == 100:
        return "CIEN"
    hundreds, rest = divmod(n, 100)
    words = [_HUNDREDS[hundreds]] if hundreds else []
    if rest:
        if rest < 10:
            words.append(_UNITS[rest])
        elif rest < 20:
            words.append(_TEENS[rest - 10])
        elif rest < 30:
            words.append("VEINTE" if rest == 20 else f"VEINTI{_UNITS[rest - 20]}")
        else:
            tens, units = divmod(rest, 10)
            words.append(_TENS[tens] if not units else f"{_TENS[tens]} Y {_UNITS[units]}")
    return " ".join(w for w in words if w)


def number_to_words_es(n: int) -> str:
    """Entero no negativo (hasta 999 999 999) en palabras, mayúsculas."""
    if n < 0:
        raise ValueError("Solo enteros no negativos")
    if n == 0:
        return "CERO"
    if n >= 1_000_000_000:
        raise ValueError("Importe fuera de rango para la leyenda")
    millions, rest = divmod(n, 1_000_000)
    thousands, units = divmod(rest, 1_000)
    parts: list[str] = []
    if millions:
        parts.append("UN MILLÓN" if millions == 1 else f"{_below_thousand(millions)} MILLONES")
    if thousands:
        parts.append("MIL" if thousands == 1 else f"{_below_thousand(thousands)} MIL")
    if units:
        parts.append(_below_thousand(units))
    return " ".join(parts).replace("UNO MIL", "UN MIL")


def amount_in_words(total: Decimal, currency: str) -> str:
    """Leyenda 1000: ``CUARENTA CON 00/100 SOLES``."""
    whole = int(total)
    cents = int((total - whole) * 100)
    currency_words = CURRENCY_WORDS.get(currency.upper(), currency.upper())
    return f"{number_to_words_es(whole)} CON {cents:02d}/100 {currency_words}"


# --- Plantilla --------------------------------------------------------------
def _text(value) -> dict[str, Any]:
    return {"_text": str(value)}


def _money(value: Decimal, currency: str) -> dict[str, Any]:
    return {"_attributes": {"currencyID": currency}, "_text": f"{value:.2f}"}


def _tax_scheme() -> dict[str, Any]:
    return {
        "cbc:ID": _text("1000"),
        "cbc:Name": _text("IGV"),
        "cbc:TaxTypeCode": _text("VAT"),
    }


def build_document_body(draft: InvoiceDraft, issuer: IssuerParty, customer: CustomerParty) -> dict[str, Any]:
    if draft.document_type is BillingDocumentType.factura and customer.doc_type != SUNAT_IDENTITY_RUC:
        raise ValueError("Una factura exige un adquirente con RUC")
    if draft.document_type is BillingDocumentType.boleta and customer.doc_type == SUNAT_IDENTITY_RUC:
        raise ValueError("A un cliente con RUC le corresponde factura, no boleta")

    cur = draft.currency.upper()
    a = draft.amounts
    customer_party: dict[str, Any] = {
        "cac:PartyIdentification": {
            "cbc:ID": {"_attributes": {"schemeID": customer.doc_type}, "_text": customer.doc_number}
        },
        "cac:PartyLegalEntity": {"cbc:RegistrationName": _text(customer.name)},
    }
    if customer.address:
        customer_party["cac:PartyLegalEntity"]["cac:RegistrationAddress"] = {
            "cac:AddressLine": {"cbc:Line": _text(customer.address)}
        }

    line_tax_subtotal = {
        "cbc:TaxableAmount": _money(a.taxable, cur),
        "cbc:TaxAmount": _money(a.igv, cur),
        "cac:TaxCategory": {
            "cbc:Percent": _text(f"{a.igv_percent:.2f}".rstrip("0").rstrip(".")),
            "cbc:TaxExemptionReasonCode": _text("10"),
            "cac:TaxScheme": _tax_scheme(),
        },
    }

    return {
        "cbc:UBLVersionID": _text("2.1"),
        "cbc:CustomizationID": _text("2.0"),
        "cbc:ID": _text(draft.full_number),
        "cbc:IssueDate": _text(draft.issue_date.isoformat()),
        "cbc:IssueTime": _text(draft.issue_time.strftime("%H:%M:%S")),
        "cbc:InvoiceTypeCode": {"_attributes": {"listID": "0101"}, "_text": draft.document_type.value},
        "cbc:Note": [
            {"_attributes": {"languageLocaleID": "1000"}, "_text": amount_in_words(a.total, cur)}
        ],
        "cbc:DocumentCurrencyCode": _text(cur),
        "cac:AccountingSupplierParty": {
            "cac:Party": {
                "cac:PartyIdentification": {
                    "cbc:ID": {"_attributes": {"schemeID": SUNAT_IDENTITY_RUC}, "_text": issuer.ruc}
                },
                "cac:PartyName": {"cbc:Name": _text(issuer.trade_name)},
                "cac:PartyLegalEntity": {
                    "cbc:RegistrationName": _text(issuer.name),
                    "cac:RegistrationAddress": {
                        "cbc:ID": _text(issuer.ubigeo),
                        "cbc:AddressTypeCode": _text("0000"),
                        "cbc:CityName": _text(issuer.province),
                        "cbc:CountrySubentity": _text(issuer.department),
                        "cbc:District": _text(issuer.district),
                        "cac:AddressLine": {"cbc:Line": _text(issuer.address)},
                        "cac:Country": {"cbc:IdentificationCode": _text("PE")},
                    },
                },
            }
        },
        "cac:AccountingCustomerParty": {"cac:Party": customer_party},
        "cac:PaymentTerms": [
            {"cbc:ID": _text("FormaPago"), "cbc:PaymentMeansID": _text("Contado")}
        ],
        "cac:TaxTotal": {
            "cbc:TaxAmount": _money(a.igv, cur),
            "cac:TaxSubtotal": [
                {
                    "cbc:TaxableAmount": _money(a.taxable, cur),
                    "cbc:TaxAmount": _money(a.igv, cur),
                    "cac:TaxCategory": {"cac:TaxScheme": _tax_scheme()},
                }
            ],
        },
        "cac:LegalMonetaryTotal": {
            "cbc:LineExtensionAmount": _money(a.taxable, cur),
            "cbc:TaxInclusiveAmount": _money(a.total, cur),
            "cbc:PayableAmount": _money(a.total, cur),
        },
        "cac:InvoiceLine": [
            {
                "cbc:ID": _text("1"),
                "cbc:InvoicedQuantity": {"_attributes": {"unitCode": "ZZ"}, "_text": "1"},
                "cbc:LineExtensionAmount": _money(a.taxable, cur),
                "cac:PricingReference": {
                    "cac:AlternativeConditionPrice": {
                        "cbc:PriceAmount": _money(a.total, cur),
                        "cbc:PriceTypeCode": _text("01"),
                    }
                },
                "cac:TaxTotal": {
                    "cbc:TaxAmount": _money(a.igv, cur),
                    "cac:TaxSubtotal": [line_tax_subtotal],
                },
                "cac:Item": {"cbc:Description": _text(draft.item_description)},
                "cac:Price": {"cbc:PriceAmount": _money(a.taxable, cur)},
            }
        ],
    }


def issue_moment(now: Optional[datetime] = None) -> tuple[date, time]:
    """Fecha y hora de emisión en hora de Lima (UTC−5, sin horario de verano)."""
    from datetime import timedelta, timezone

    lima = timezone(timedelta(hours=-5))
    moment = (now or datetime.now(timezone.utc)).astimezone(lima)
    return moment.date(), moment.time().replace(microsecond=0)
