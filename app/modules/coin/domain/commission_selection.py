"""One bracket policy for official quotes and transaction registration."""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from math import isfinite


def normalize_amount(value) -> float:
    """Única política de precisión para cotizar, elegir tramo, registrar y persistir:
    2 decimales con redondeo comercial (mitad hacia arriba). Sin esto, 1000.004 se
    cotizaba en un tramo (1000.00) y se registraba en otro (1000.004)."""
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("El monto debe ser un número válido") from exc
    if not amount.is_finite():
        raise ValueError("El monto debe ser positivo y finito")
    return float(amount)


def select_commission(amount, rows):
    if not isfinite(float(amount)) or amount <= 0:
        raise ValueError("El monto debe ser positivo y finito")
    ordered = sorted(rows, key=lambda row: (
        float(row.min_amount) if row.min_amount is not None else float("-inf"),
        float(row.max_amount) if row.max_amount is not None else float("inf"),
        str(row.id) if getattr(row, "id", None) else ""))
    if not ordered:
        raise ValueError("No existe una comisión configurada para el par de monedas")
    for row in ordered:
        lower = float(row.min_amount) if row.min_amount is not None else float("-inf")
        upper = float(row.max_amount) if row.max_amount is not None else float("inf")
        if ((row.min_amount is not None and not isfinite(lower)) or
                (row.max_amount is not None and not isfinite(upper)) or lower > upper):
            raise ValueError("Rango de comisión no válido")
        if lower <= amount <= upper:
            return row
    # Preserve established outer-bracket behavior; an internal gap is not a rate.
    if ordered[0].min_amount is not None and amount < float(ordered[0].min_amount):
        return ordered[0]
    highest = max(ordered, key=lambda row: float(row.max_amount) if row.max_amount is not None else float("inf"))
    if highest.max_amount is not None and amount > float(highest.max_amount):
        return highest
    raise ValueError("No hay comisión configurada para ese monto")
