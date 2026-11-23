"""Prevent a new fiscal emission for operations already dated outside the flow."""

BILLING_DATE_WITHOUT_INVOICE = (
    "Esta operación ya tiene fecha de facturación y no tiene un comprobante vinculado. "
    "La emisión está bloqueada; revisa la facturación registrada."
)


def ensure_billing_date_allows_issue(transaction, *, has_invoice: bool = False) -> None:
    if getattr(transaction, "billing_date", None) is not None and not has_invoice:
        raise ValueError(BILLING_DATE_WITHOUT_INVOICE)
