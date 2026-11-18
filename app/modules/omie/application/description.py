"""Description sent to Omie, generated from the actual remittance amounts."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def service_description(transaction, rate, service_name: str) -> str:
    def money(value):
        try:
            amount = Decimal(str(value))
            if not amount.is_finite() or amount <= 0:
                raise ValueError()
            return f"{amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}".translate(str.maketrans(",.", ".,"))
        except (InvalidOperation, ValueError):
            raise ValueError("Completa los montos de envío y recepción antes de emitir con Omie") from None

    def currency(value):
        return str(getattr(value, "value", value)).upper()

    return (
        f"{service_name.strip() or 'Remessa internacional'}\n"
        f"Operação Brasper: {transaction.code}\n"
        f"Valor enviado: {currency(rate.coin_a)} {money(transaction.origin_amount)}\n"
        f"Valor a receber: {currency(rate.coin_b)} {money(transaction.destination_amount)}"
    )


def saved_description(snapshot: dict | None) -> str:
    # Read what was reserved/sent; never regenerate historical fiscal text from
    # today's transaction values. Older notes may have no stored description.
    snapshot = snapshot or {}
    items = snapshot.get("order", {}).get("ServicosPrestados", [])
    if items:
        return str(items[0].get("cDescServ") or "")
    return str(snapshot.get("description") or "")
