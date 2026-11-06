# app/modules/billing/domain/amounts.py
"""Importes del comprobante, siempre con ``Decimal`` y ``ROUND_HALF_UP``.

El importe facturable es Venta final de Contabilidad, con impuesto incluido.
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


def accounting_final_sale(origin_amount, sales_percentage, discount_percentage=None,
                          *, amount_threshold=100, fixed_commission=3) -> Optional[Decimal]:
    """Venta final de la hoja: comisión del cliente × (1 − descuento variable).

    Replica la columna de Contabilidad, sin reutilizar commission_result.
    La comisión del cliente se redondea antes de aplicar el descuento.
    """
    if origin_amount is None:
        return None
    amount = to_decimal(origin_amount)
    if not amount.is_finite() or amount <= 0:
        return None
    threshold = to_decimal(amount_threshold)
    fixed = to_decimal(fixed_commission)
    if not threshold.is_finite() or threshold <= 0 or not fixed.is_finite() or fixed < 0:
        raise ValueError("Configuración de comisión contable inválida")
    if amount < threshold:
        return money(fixed)
    if sales_percentage is None:
        return None
    percentage = to_decimal(sales_percentage)
    if not percentage.is_finite() or percentage < 0:
        return None
    if discount_percentage is None:
        discount_percentage = next((p for limit, p in (
            (300, 40), (1000, 45), (2000, 50), (3000, 55),
            (5000, 60), (7000, 65), (10000, 70)
        ) if amount < limit), 75)
    discount = to_decimal(discount_percentage)
    if not discount.is_finite() or not 0 <= discount <= 100:
        raise ValueError("Descuento variable contable inválido")
    commission = money(amount * percentage / 100)
    return money(commission * (1 - discount / 100))
