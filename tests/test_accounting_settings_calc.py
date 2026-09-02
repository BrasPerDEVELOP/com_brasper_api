"""Cálculo de importes contables con settings globales (umbral + fijo)."""
from app.modules.coin.domain.accounting_settings_calc import (
    compute_transaction_accounting_amounts,
)


def test_under_threshold_uses_fixed_commission():
    amounts = compute_transaction_accounting_amounts(
        80,
        accounting_percentage=45,
        amount_threshold=100,
        fixed_commission=3,
    )
    assert amounts is not None
    assert amounts.accounting_commision == 3.0
    assert amounts.accounting_destination_amount == 77.0
    assert amounts.accounting_tax_final == 0.54


def test_under_threshold_does_not_need_percentage():
    amounts = compute_transaction_accounting_amounts(
        50,
        accounting_percentage=None,
        amount_threshold=100,
        fixed_commission=3,
    )
    assert amounts is not None
    assert amounts.accounting_commision == 3.0


def test_at_or_above_threshold_uses_percentage():
    amounts = compute_transaction_accounting_amounts(
        500,
        accounting_percentage=45,
        amount_threshold=100,
        fixed_commission=3,
    )
    assert amounts is not None
    assert amounts.accounting_commision == 225.0
    assert amounts.accounting_destination_amount == 275.0
    assert amounts.accounting_tax_final == 40.5


def test_zero_or_missing_amount_returns_none():
    assert compute_transaction_accounting_amounts(0, 45) is None
    assert compute_transaction_accounting_amounts(None, 45) is None


def test_above_threshold_without_percentage_returns_none():
    assert (
        compute_transaction_accounting_amounts(
            200,
            accounting_percentage=None,
            amount_threshold=100,
            fixed_commission=3,
        )
        is None
    )


def test_custom_settings_change_the_cutoff():
    amounts = compute_transaction_accounting_amounts(
        150,
        accounting_percentage=40,
        amount_threshold=200,
        fixed_commission=5,
    )
    assert amounts is not None
    assert amounts.accounting_commision == 5.0
