"""Los cupones descuentan entre 0 y 100% de la comisión, incluidos extremos."""
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.transactions.application.schemas.coupon_schema import CouponCreateCmd, CouponUpdateCmd


@pytest.mark.parametrize("percentage", [0, 25, 99.5, 100])
def test_coupon_percentage_valid_on_create_and_update(percentage):
    values = dict(code="TEST", discount_percentage=percentage, max_uses=10,
                  origin_currency="PEN", destination_currency="BRL")
    assert CouponCreateCmd(**values).discount_percentage == percentage
    assert CouponUpdateCmd(id=uuid4(), discount_percentage=percentage).discount_percentage == percentage


@pytest.mark.parametrize("percentage", [-1, 100.01, float("nan"), float("inf"), float("-inf")])
def test_coupon_percentage_invalid_on_create_and_update(percentage):
    with pytest.raises(ValidationError):
        CouponCreateCmd(code="TEST", discount_percentage=percentage, max_uses=10,
                        origin_currency="PEN", destination_currency="BRL")
    with pytest.raises(ValidationError):
        CouponUpdateCmd(id=uuid4(), discount_percentage=percentage)
