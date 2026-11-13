from types import SimpleNamespace
from datetime import datetime, timezone
from uuid import uuid4
import pytest
from app.modules.coin.domain.commission_selection import select_commission
from app.modules.coin.domain.enums import Currency
from app.modules.brasper.application.campaign_quote import calculate, inverse_quote


def row(lower, upper, percent):
    return SimpleNamespace(id=uuid4(), min_amount=lower, max_amount=upper, percentage=percent)


def test_minimum_and_internal_gaps_are_rejected_but_maximum_uses_highest_bracket():
    low, high = row(100, 1000, 3), row(1100, 10000, 2)
    with pytest.raises(ValueError, match="mínimo.*100"):
        select_commission(50, [high, low])
    assert select_commission(100, [high, low]) is low
    assert select_commission(25000, [high, low]) is high
    assert select_commission(1000, [high, low]) is low
    with pytest.raises(ValueError): select_commission(1050, [high, low])
    with pytest.raises(ValueError): select_commission(float("nan"), [low])
    with pytest.raises(ValueError): select_commission(100, [row(float("nan"), 1000, 3)])


def test_quote_and_inverse_reject_amounts_below_minimum():
    commissions = [row(100, 1000, 3), row(1100, 10000, 2)]
    history = SimpleNamespace(completed_transfers=0, pending_transfers=0)
    def compute(amount):
        return calculate(amount, 1.5, commissions, [], {}, history, Currency.pen, Currency.brl, datetime.now(timezone.utc))
    with pytest.raises(ValueError, match="mínimo.*100"):
        compute(50)
    with pytest.raises(ValueError):
        inverse_quote(10, 1.5, commissions, [], compute)
    for amount in [100, 25000]:
        quote = compute(amount)
        assert quote["commission_rate"] == select_commission(amount, commissions).percentage
        inverse = inverse_quote(quote["amount_receive"], 1.5, commissions, [], compute)
        assert inverse["amount_send"] == amount


def test_internal_operator_policy_uses_first_bracket_for_small_transfers():
    low, high = row(100, 1000, 3), row(1100, 10000, 2)
    assert select_commission(50, [high, low], allow_below_minimum=True) is low
    with pytest.raises(ValueError, match="mínimo.*100"):
        select_commission(50, [high, low])
