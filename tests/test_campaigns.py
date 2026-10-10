from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.modules.transactions.application.schemas.campaign_schema import CampaignRules
from app.modules.transactions.application.campaign_policy import discount_for
from app.modules.transactions.application.use_cases.transaction_use_cases import release_coupon_usage
from app.modules.brasper.application.campaign_quote import calculate, inverse_quote
from app.modules.brasper.application.ai_schemas import AIClientHistoryDTO
from app.modules.coin.domain.enums import Currency


def rules(**overrides):
    return CampaignRules(segment="first_transfer", messages={"es": {"text": "Condiciones ES"}, "pt": {"text": "Condições PT"}},
                         **overrides).model_dump(mode="json")


def coupon(**overrides):
    values = dict(id=uuid4(), code="PRIMER25", discount_percentage=25, campaign_rules=rules(),
                  origin_currency=Currency.pen, destination_currency=Currency.brl, exchange_rate_scopes=None,
                  is_active=True, lifecycle_status="ACTIVE", max_uses=100, used_count=0, per_user_limit=1,
                  start_date=None, end_date=None, published_version=1)
    return SimpleNamespace(**{**values, **overrides})


def test_campaign_validation_rejects_missing_translations_and_inverted_limits():
    with pytest.raises(ValidationError):
        CampaignRules(segment="first_transfer", messages={"es": {"text": "Hola"}})
    with pytest.raises(ValidationError):
        rules(minimum_amount=500, maximum_amount=100)
    with pytest.raises(ValidationError):
        rules(timezone="Not/AZone")


def test_first_transfer_pending_reservation_and_cap():
    c = coupon(campaign_rules=rules(maximum_discount=2))
    assert discount_for(c, 500, 15, completed=0, pending=0) == 2
    for completed, pending in [(1, 0), (0, 1)]:
        with pytest.raises(ValueError, match="reservado"):
            discount_for(c, 500, 15, completed=completed, pending=pending)
    # A failed/cancelled operation is excluded from pending by the history query.
    assert discount_for(c, 500, 15, completed=0, pending=0) == 2


def test_quote_priority_limits_and_inverse_cap():
    commissions = [SimpleNamespace(min_amount=0, max_amount=100000, percentage=3)]
    a = coupon(campaign_rules=rules(maximum_discount=2, priority=20))
    b = coupon(discount_percentage=100, campaign_rules=rules(priority=1))
    history = AIClientHistoryDTO(completed_transfers=0, pending_transfers=0, first_transfer_eligible=True)
    now = datetime.now(timezone.utc)
    def compute(amount, uses=None):
        return calculate(amount, 1.5, commissions, [a, b], uses or {}, history, Currency.pen, Currency.brl, now)
    q = compute(500)
    assert q["coupon_id"] == str(a.id) and q["coupon_savings_amount"] == 2 and not q["reserved"]
    assert compute(500, {a.id: 1})["coupon_id"] == str(b.id)
    inv = inverse_quote(q["amount_receive"], 1.5, commissions, [a, b], compute)
    assert abs(inv["amount_send"] - 500) <= 0.01
    a.is_active = b.is_active = False
    assert compute(500)["coupon_id"] is None


async def test_release_redemption_is_idempotent():
    c = coupon(used_count=1)
    redemption = SimpleNamespace(deleted=False)
    session = MagicMock()
    coupon_result = SimpleNamespace(scalar_one_or_none=lambda: c)
    redemption_result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [] if redemption.deleted else [redemption]))
    session.execute = AsyncMock(side_effect=[coupon_result, redemption_result, coupon_result, redemption_result])
    transaction = SimpleNamespace(id=uuid4(), coupon_id=c.id, status="failed")
    await release_coupon_usage(session, transaction)
    await release_coupon_usage(session, transaction)
    assert redemption.deleted and c.used_count == 0


async def test_completed_coupon_cannot_be_released():
    from app.modules.transactions.domain.enums import TransactionStatus
    session = MagicMock()
    session.execute = AsyncMock()
    with pytest.raises(ValueError, match="completada"):
        await release_coupon_usage(session, SimpleNamespace(status=TransactionStatus.completed))
    session.execute.assert_not_called()


def test_coupon_edits_cannot_bypass_ledger_or_erase_completed_history():
    from app.modules.transactions.application.use_cases.transaction_use_cases import validate_coupon_edit
    from app.modules.transactions.domain.enums import TransactionStatus
    from decimal import Decimal
    entity = SimpleNamespace(coupon_id=uuid4(), user_id=uuid4(), status=TransactionStatus.verification,
                             origin_amount=Decimal("500.00"))
    validate_coupon_edit(entity, {"origin_amount": 500.0, "status": TransactionStatus.failed})
    for change in [{"coupon_id": None}, {"coupon_id": uuid4()}, {"user_id": uuid4()}, {"origin_amount": 600}]:
        with pytest.raises(ValueError):
            validate_coupon_edit(entity, change)
    entity.status = TransactionStatus.completed
    for coupon_id in [entity.coupon_id, None]:
        entity.coupon_id = coupon_id
        with pytest.raises(ValueError, match="completada"):
            validate_coupon_edit(entity, {"status": TransactionStatus.failed})
        with pytest.raises(ValueError, match="completada"):
            validate_coupon_edit(entity, {"user_id": uuid4()})


def test_campaign_admin_and_quote_routes_were_removed_from_the_api():
    """Las campañas viven solo en com_brasper_ia: la API no expone administración ni cotización IA."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.settings import get_settings
    paths = set(app.openapi()["paths"])
    assert not any("/ai/admin/campaigns" in path for path in paths)
    assert "/brasper/ai/quotes" not in paths
    assert not hasattr(get_settings(), "BRASPER_IA_ADMIN_SECRET")
    client = TestClient(app)
    assert client.get("/brasper/ai/admin/campaigns").status_code == 404
    assert client.post("/brasper/ai/quotes", json={}).status_code in (404, 405)
    # Identity linking and client lookups stay available.
    for kept in ("/brasper/ai/clients/lookup", "/brasper/ai/clients/upsert", "/brasper/ai/deposit-accounts",
                 "/brasper/ai/clients/{user_id}/history", "/brasper/ai/clients/{user_id}/operations",
                 "/brasper/identity-links", "/brasper/ai/identity-links/redeem"):
        assert kept in paths
