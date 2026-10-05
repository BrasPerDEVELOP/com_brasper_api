"""Importes del comprobante: Decimal, ROUND_HALF_UP y las dos lecturas del IGV."""
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.modules.billing.domain.amounts import billable_amount, compute_invoice_amounts, money


def test_igv_incluido_en_la_comision():
    amounts = compute_invoice_amounts(40.0, igv_included=True)
    assert amounts.taxable == Decimal("33.90")
    assert amounts.igv == Decimal("6.10")
    assert amounts.total == Decimal("40.00")
    assert amounts.taxable + amounts.igv == amounts.total


def test_igv_sumado_a_la_comision():
    amounts = compute_invoice_amounts(40.0, igv_included=False)
    assert amounts.taxable == Decimal("40.00")
    assert amounts.igv == Decimal("7.20")
    assert amounts.total == Decimal("47.20")


@pytest.mark.parametrize("value", [None, 0, 0.0, -5, Decimal("0.00")])
def test_sin_comision_no_hay_comprobante(value):
    assert compute_invoice_amounts(value) is None


def test_redondeo_half_up_y_sin_ruido_de_float():
    # 101.87 / 1.18 = 86.3305… → 86.33 ; IGV = 15.54 (no 15.53 como daría round() de Python en otros casos)
    amounts = compute_invoice_amounts(101.87)
    assert amounts.taxable == Decimal("86.33")
    assert amounts.igv == Decimal("15.54")
    assert money(0.1 + 0.2) == Decimal("0.30")
    # 2.675 con float se vuelve 2.67499…; con str() y ROUND_HALF_UP debe dar 2.68
    assert money("2.675") == Decimal("2.68")


def test_la_base_suma_siempre_al_total():
    for cents in range(100, 300000, 7):
        total = Decimal(cents) / 100
        amounts = compute_invoice_amounts(total)
        assert amounts.taxable + amounts.igv == amounts.total == total


def test_billable_amount_usa_la_comision_efectiva():
    tx = SimpleNamespace(commission_result=12.3456)
    assert billable_amount(tx) == Decimal("12.35")
    assert billable_amount(SimpleNamespace(commission_result=None)) is None
