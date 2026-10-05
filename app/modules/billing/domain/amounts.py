# app/modules/billing/domain/amounts.py
"""Importes del comprobante, siempre con ``Decimal`` y ``ROUND_HALF_UP``.

Solo se factura la comisión cobrada al cliente. ``Transaction.commission_result``
ya es la comisión efectiva (descontado el cupón o el ajuste de la calculadora
especial), así que es el importe total del comprobante.

Dos lecturas posibles de ese importe, que decide ``BILLING_COMMISSION_INCLUDES_IGV``:

- incluye IGV (por defecto): base = total / (1 + IGV), IGV = total − base.
- no lo incluye: base = total, IGV = base × tasa, total = base + IGV.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

MONEY = Decimal("0.01")
DEFAULT_IGV_RATE = Decimal("0.18")


def to_decimal(value) -> Decimal:
    """Convierte float/str/Decimal sin arrastrar el ruido binario del float."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def money(value) -> Decimal:
    return to_decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class InvoiceAmounts:
    taxable: Decimal  # valor de venta (base imponible)
    igv: Decimal
    total: Decimal  # importe total del comprobante
    igv_rate: Decimal

    @property
    def igv_percent(self) -> Decimal:
        return (self.igv_rate * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_invoice_amounts(
    total_charged,
    *,
    igv_included: bool = True,
    igv_rate=DEFAULT_IGV_RATE,
) -> Optional[InvoiceAmounts]:
    """Devuelve los tres importes o ``None`` si no hay nada que facturar (≤ 0)."""
    if total_charged is None:
        return None
    charged = to_decimal(total_charged)
    if charged.is_nan() or charged <= 0:
        return None
    rate = to_decimal(igv_rate)
    if igv_included:
        total = money(charged)
        taxable = money(total / (Decimal(1) + rate))
        igv = total - taxable
    else:
        taxable = money(charged)
        igv = money(taxable * rate)
        total = taxable + igv
    return InvoiceAmounts(taxable=taxable, igv=igv, total=total, igv_rate=rate)


def billable_amount(transaction) -> Optional[Decimal]:
    """Comisión efectivamente cobrada en la operación (lo que entra al comprobante)."""
    value = getattr(transaction, "commission_result", None)
    if value is None:
        return None
    return money(value)
