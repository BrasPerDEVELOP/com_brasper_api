"""Restore UBL element order at the APISUNAT transport boundary.

PostgreSQL JSONB preserves values, but not object key order. APISUNAT converts
documentBody keys to XML elements, whose sequence matters in UBL 2.1. Never
rebuild a retry from current customer/transaction data: reorder its snapshot.

Sequences below cover the nodes produced by ubl_builder, in UBL 2.1 order:
https://docs.oasis-open.org/ubl/os-UBL-2.1/xsd/maindoc/UBL-Invoice-2.1.xsd
https://docs.oasis-open.org/ubl/os-UBL-2.1/xsd/common/UBL-CommonAggregateComponents-2.1.xsd
Extend these sequences when adding new elements to the invoice template.
"""
from typing import Any


_SEQUENCES = {
    "Invoice": (
        "cbc:UBLVersionID", "cbc:CustomizationID", "cbc:ID", "cbc:IssueDate",
        "cbc:IssueTime", "cbc:InvoiceTypeCode", "cbc:Note",
        "cbc:DocumentCurrencyCode", "cac:AccountingSupplierParty",
        "cac:AccountingCustomerParty", "cac:PaymentTerms", "cac:TaxTotal",
        "cac:LegalMonetaryTotal", "cac:InvoiceLine",
    ),
    "cac:Party": (
        "cac:PartyIdentification", "cac:PartyName", "cac:PartyLegalEntity",
    ),
    "cac:PartyLegalEntity": ("cbc:RegistrationName", "cac:RegistrationAddress"),
    "cac:RegistrationAddress": (
        "cbc:ID", "cbc:AddressTypeCode", "cbc:CityName", "cbc:CountrySubentity",
        "cbc:District", "cac:AddressLine", "cac:Country",
    ),
    "cac:PaymentTerms": ("cbc:ID", "cbc:PaymentMeansID"),
    "cac:TaxTotal": ("cbc:TaxAmount", "cac:TaxSubtotal"),
    "cac:TaxSubtotal": ("cbc:TaxableAmount", "cbc:TaxAmount", "cac:TaxCategory"),
    "cac:TaxCategory": ("cbc:Percent", "cbc:TaxExemptionReasonCode", "cac:TaxScheme"),
    "cac:TaxScheme": ("cbc:ID", "cbc:Name", "cbc:TaxTypeCode"),
    "cac:LegalMonetaryTotal": (
        "cbc:LineExtensionAmount", "cbc:TaxInclusiveAmount", "cbc:PayableAmount",
    ),
    "cac:InvoiceLine": (
        "cbc:ID", "cbc:InvoicedQuantity", "cbc:LineExtensionAmount",
        "cac:PricingReference", "cac:TaxTotal", "cac:Item", "cac:Price",
    ),
    "cac:AlternativeConditionPrice": ("cbc:PriceAmount", "cbc:PriceTypeCode"),
}


def ordered_document_body(body: dict[str, Any]) -> dict[str, Any]:
    """Copy the snapshot with ordered XML children; preserve all values/lists.

Unknown keys are retained, never silently discarded. This is serialization,
not schema validation, and does not change the stored document.
"""
    def visit(value: Any, element: str) -> Any:
        if isinstance(value, list):
            return [visit(item, element) for item in value]
        if not isinstance(value, dict):
            return value
        order = ("_attributes", "_text", *_SEQUENCES.get(element, ()))
        ranks = {key: rank for rank, key in enumerate(order)}
        return {
            key: visit(value[key], key)
            for key in sorted(value, key=lambda key: ranks.get(key, len(order)))
        }

    return visit(body, "Invoice")
