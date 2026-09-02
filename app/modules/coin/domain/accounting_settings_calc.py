"""Cálculo de importes contables por transacción usando settings globales.

Regla (hoja Brasper + ``coin.commission_accounting_settings``):

    si origin_amount == 0        → sin comisión
    si origin_amount < umbral    → fixed_commission
    si no                        → origin_amount × (percentage / 100)

Luego:

    accounting_destination_amount = origin − comisión
    accounting_tax_final          = comisión × IGV (18%)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


DEFAULT_AMOUNT_THRESHOLD = 100.0
DEFAULT_FIXED_COMMISSION = 3.0
DEFAULT_IGV_RATE = 0.18
MONEY_SCALE = 2


def _round_money(value: float) -> float:
    return round(value, MONEY_SCALE)


@dataclass(frozen=True)
class TransactionAccountingAmounts:
    accounting_commision: float
    accounting_destination_amount: float
    accounting_tax_final: float


def compute_transaction_accounting_amounts(
    origin_amount: Optional[float],
    accounting_percentage: Optional[float],
    *,
    amount_threshold: float = DEFAULT_AMOUNT_THRESHOLD,
    fixed_commission: float = DEFAULT_FIXED_COMMISSION,
    igv_rate: float = DEFAULT_IGV_RATE,
) -> Optional[TransactionAccountingAmounts]:
    """Calcula los tres importes contables de una transacción.

    Devuelve ``None`` cuando no hay monto (o es 0) o, por encima del umbral,
    cuando falta el porcentaje del tramo de contabilidad.
    """
    if origin_amount is None:
        return None
    amount = float(origin_amount)
    if not amount or amount != amount:  # NaN / 0
        return None

    threshold = float(amount_threshold) if amount_threshold is not None else DEFAULT_AMOUNT_THRESHOLD
    fixed = float(fixed_commission) if fixed_commission is not None else DEFAULT_FIXED_COMMISSION
    if threshold <= 0:
        threshold = DEFAULT_AMOUNT_THRESHOLD
    if fixed < 0:
        fixed = DEFAULT_FIXED_COMMISSION

    if amount < threshold:
        commission = _round_money(fixed)
    else:
        if accounting_percentage is None:
            return None
        pct = float(accounting_percentage)
        if pct != pct:  # NaN
            return None
        commission = _round_money(amount * pct / 100)

    destination = _round_money(amount - commission)
    tax = _round_money(commission * float(igv_rate))
    return TransactionAccountingAmounts(
        accounting_commision=commission,
        accounting_destination_amount=destination,
        accounting_tax_final=tax,
    )
