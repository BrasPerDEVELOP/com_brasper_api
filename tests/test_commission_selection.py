from types import SimpleNamespace
from datetime import datetime, timezone
from uuid import uuid4
import pytest
from app.modules.coin.domain.commission_selection import select_commission
from app.modules.coin.domain.enums import Currency
from app.modules.brasper.application.campaign_quote import calculate, inverse_quote


def row(lower, upper, percent):
    return SimpleNamespace(id=uuid4(), min_amount=lower, max_amount=upper, percentage=percent)


def test_outer_brackets_preserve_registration_policy_and_gaps_fail():
    low, high = row(100, 1000, 3), row(1100, 10000, 2)
    assert select_commission(50, [high, low]) is low
    assert select_commission(25000, [high, low]) is high
    assert select_commission(1000, [high, low]) is low
    with pytest.raises(ValueError): select_commission(1050, [high, low])
    with pytest.raises(ValueError): select_commission(float("nan"), [low])
    with pytest.raises(ValueError): select_commission(100, [row(float("nan"), 1000, 3)])


def test_quote_and_inverse_use_same_outer_brackets():
    commissions = [row(100, 1000, 3), row(1100, 10000, 2)]
    history = SimpleNamespace(completed_transfers=0, pending_transfers=0)
    def compute(amount):
        return calculate(amount, 1.5, commissions, [], {}, history, Currency.pen, Currency.brl, datetime.now(timezone.utc))
    for amount in [50, 25000]:
        quote = compute(amount)
        assert quote["commission_rate"] == select_commission(amount, commissions).percentage
        inverse = inverse_quote(quote["amount_receive"], 1.5, commissions, [], compute)
        assert inverse["amount_send"] == amount
