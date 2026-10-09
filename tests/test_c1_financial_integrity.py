"""C1 - Integridad financiera de promociones (auditoría 2026-10-09).

Sin PostgreSQL real: los bloqueos se verifican por el ORDEN y la forma de las
sentencias (``FOR UPDATE``) que el caso de uso envía a una sesión falsa; la
exclusión real entre transacciones concurrentes NO queda demostrada aquí.
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.brasper.application.campaign_quote import calculate, inverse_quote
from app.modules.coin.domain.enums import Currency
from app.modules.transactions.application.campaign_policy import discount_state
from app.modules.transactions.application.schemas.coupon_schema import CouponUpdateCmd
from app.modules.transactions.application.schemas.transaction_schema import (
    TransactionCreateCmd,
    TransactionReadDTO,
    TransactionUpdateCmd,
)
from app.modules.transactions.application.use_cases.coupon_use_cases import (
    DeleteCouponUseCase,
    UpdateCouponUseCase,
)
from app.modules.transactions.application.use_cases.transaction_use_cases import (
    CreateTransactionUseCase,
    DeleteTransactionUseCase,
    UpdateTransactionUseCase,
)
from app.modules.transactions.domain.enums import TransactionStatus
from app.modules.transactions.domain.models import Coupon, CouponRedemption, Transaction
from app.modules.users.domain.models import User

RATE = 1.5
NOW = datetime.now(timezone.utc)


def _rules(**overrides):
    return {"segment": "all", "messages": {"es": {"text": "Condiciones"}, "pt": {"text": "Condições"}},
            **overrides}


def _commission(lower, upper, percentage):
    return SimpleNamespace(id=uuid4(), min_amount=lower, max_amount=upper, percentage=percentage,
                           coin_a=Currency.pen, coin_b=Currency.brl)


def _coupon(**overrides):
    values = dict(id=uuid4(), code="CAMP50", discount_percentage=50, campaign_rules=_rules(maximum_discount=3, priority=5),
                  origin_currency=Currency.pen, destination_currency=Currency.brl, exchange_rate_scopes=None,
                  is_active=True, lifecycle_status="ACTIVE", max_uses=100, used_count=0, per_user_limit=1,
                  start_date=None, end_date=None, published_version=7, coupon_type="CAMPAIGN", deleted=False)
    return SimpleNamespace(**{**values, **overrides})


class _Result:
    def __init__(self, value=None, rows=None):
        self._value, self._rows = value, rows or []

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self._rows))


def _entity_of(stmt):
    return stmt.column_descriptions[0].get("entity")


class LedgerSession:
    """Sesión falsa que registra el orden de bloqueos y modela el registro de usos."""

    def __init__(self, *, coupon=None, transaction=None, owner=None, redemptions=None,
                 completed=0, pending=0):
        self.coupon, self.transaction, self.owner = coupon, transaction, owner
        self.redemptions = redemptions if redemptions is not None else []
        self.completed, self.pending = completed, pending
        self.locks: list[str] = []
        self.added: list = []

    async def execute(self, stmt):
        entity = _entity_of(stmt)
        if "FOR UPDATE" in str(stmt):
            self.locks.append(entity.__name__)
        if entity is Coupon:
            return _Result(self.coupon)
        if entity is Transaction:
            return _Result(self.transaction)
        if entity is CouponRedemption:
            return _Result(rows=[r for r in self.redemptions if not r.deleted])
        return _Result(None)

    async def scalar(self, stmt):
        entity = _entity_of(stmt)
        sql = str(stmt)
        if entity is Transaction and "count" not in sql.lower():
            return self.owner
        if entity is CouponRedemption:
            return sum(1 for r in self.redemptions if not r.deleted)
        if entity is Transaction:
            return self.pending if "NOT IN" in sql else self.completed
        return 0

    def add(self, obj):
        self.added.append(obj)


def _create_use_case(session, commissions, client_commission):
    captured = {}
    repo = AsyncMock()

    async def add(entity):
        entity.id = uuid4()
        captured["entity"] = entity
        return entity

    repo.add = add
    repo.next_sequential_transaction_code = AsyncMock(return_value="PxB-1")
    tax = SimpleNamespace(coin_a=Currency.pen, coin_b=Currency.brl, tax=RATE)
    tax_rate_repo = AsyncMock()
    tax_rate_repo.get = AsyncMock(return_value=tax)
    user_repo = AsyncMock()
    user_repo.list_ids_by_roles = AsyncMock(return_value=[uuid4()])
    bank_account_repo = AsyncMock()
    bank_account_repo.get = AsyncMock(return_value=MagicMock(bank_id=uuid4(), bank=MagicMock(bank="B", company="C")))
    commission_repo = AsyncMock()
    commission_repo.get = AsyncMock(return_value=client_commission)
    commission_repo.list = AsyncMock(return_value=list(commissions))
    uc = CreateTransactionUseCase(repo, tax_rate_repo, user_repo, bank_account_repo, AsyncMock(),
                                  commission_repo=commission_repo, session=session)
    return uc, captured, commission_repo


def _create_cmd(amount, *, coupon_id=None, commission_id=None, user_id=None):
    return TransactionCreateCmd(bank_account_destination=uuid4(), user_id=user_id or uuid4(), tax_rate_id=uuid4(),
                                commission_id=commission_id or uuid4(), coupon_id=coupon_id,
                                origin_amount=amount, destination_amount=1, code="")


@pytest.fixture(autouse=True)
def _stub_read_dto(monkeypatch):
    monkeypatch.setattr(TransactionReadDTO, "model_validate", lambda obj: MagicMock())


# --------------------------------------------------------------------------- #
# Cotización == registro (tramos solapados, tope, prioridad, cotización inversa)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
@pytest.mark.parametrize("amount", [500, 999.99, 1000, 1000.01, 3000])
async def test_registration_matches_official_quote_including_overlapping_bracket(amount):
    low, high = _commission(0, 1000, 5), _commission(1000, 5000, 3)
    coupon = _coupon()
    history = SimpleNamespace(completed_transfers=0, pending_transfers=0)
    quote = calculate(amount, RATE, [low, high], [coupon], {}, history, Currency.pen, Currency.brl, NOW)
    assert quote["discount_state"] == "quoted" and quote["reserved"] is False

    session = LedgerSession(coupon=coupon)
    # The client sends the cheaper overlapping bracket: registration must not honour it.
    uc, captured, commission_repo = _create_use_case(session, [high, low], client_commission=high)
    await uc.execute(_create_cmd(amount, coupon_id=coupon.id, commission_id=high.id))
    entity = captured["entity"]

    assert entity.commission_id == (low if amount <= 1000 else high).id
    assert float(entity.commission_result) == quote["commission"]
    assert float(entity.total_to_send) == quote["total_to_send"]
    assert float(entity.destination_amount) == quote["amount_receive"]
    assert float(entity.coupon_discount_commission) == quote["coupon_savings_amount"]
    assert entity.coupon_campaign_version == quote["campaign_version"] == 7
    # Discount only over the commission: capital and rate untouched.
    assert float(entity.tax_amount) == RATE
    assert float(entity.total_to_send) == round(amount - quote["commission_gross"] + quote["coupon_savings_amount"], 2)
    filters = {f.field: f.value for f in commission_repo.list.await_args.kwargs["query_filter"].filters}
    assert filters["enable"] is True


@pytest.mark.asyncio
async def test_disabled_bracket_sent_by_client_is_replaced_by_enabled_one():
    disabled = _commission(0, 5000, 1)  # not returned by the enabled-only listing
    enabled = _commission(0, 5000, 4)
    session = LedgerSession()
    uc, captured, _ = _create_use_case(session, [enabled], client_commission=disabled)
    await uc.execute(_create_cmd(200, commission_id=disabled.id))
    assert captured["entity"].commission_id == enabled.id
    assert float(captured["entity"].commission_result) == 8.0


@pytest.mark.asyncio
async def test_inverse_quote_registers_the_same_amounts():
    low, high = _commission(0, 1000, 5), _commission(1000, 5000, 3)
    coupon = _coupon(campaign_rules=_rules(maximum_discount=3, minimum_amount=800))
    history = SimpleNamespace(completed_transfers=0, pending_transfers=0)

    def compute(value):
        return calculate(value, RATE, [low, high], [coupon], {}, history, Currency.pen, Currency.brl, NOW)

    # 1000 PEN -> 1429.50 BRL and 1000.01 PEN -> 1459.50 BRL: receipts in between
    # are unreachable (bracket jump) and must go to an advisor, never be guessed.
    with pytest.raises(ValueError, match="tramo"):
        inverse_quote(1450.0, RATE, [low, high], [coupon], compute)
    for target in [700.0, 1200.0, 1429.5, 1500.0, 2000.0]:
        quote = inverse_quote(target, RATE, [low, high], [coupon], compute)
        assert abs(quote["amount_receive"] - target) <= 0.02
        session = LedgerSession(coupon=_coupon(id=coupon.id, campaign_rules=coupon.campaign_rules))
        uc, captured, _ = _create_use_case(session, [low, high], client_commission=low)
        await uc.execute(_create_cmd(quote["amount_send"], coupon_id=quote["coupon_id"] and coupon.id))
        assert float(captured["entity"].destination_amount) == quote["amount_receive"]


@pytest.mark.asyncio
async def test_coupon_is_never_stored_without_the_usage_ledger():
    uc = CreateTransactionUseCase(AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock())
    uc._tax_rate_repo.get = AsyncMock(return_value=SimpleNamespace(coin_a=Currency.pen, coin_b=Currency.brl, tax=1))
    uc._bank_account_repo.get = AsyncMock(return_value=MagicMock())
    uc._user_repo.list_ids_by_roles = AsyncMock(return_value=[uuid4()])
    with pytest.raises(ValueError, match="registro de usos"):
        await uc.execute(_create_cmd(100, coupon_id=uuid4()))
    uc.repo.add.assert_not_called()


@pytest.mark.asyncio
async def test_registration_locks_client_before_coupon_and_reserves_once():
    coupon = _coupon(campaign_rules=_rules(segment="first_transfer"))
    session = LedgerSession(coupon=coupon)
    uc, _, _ = _create_use_case(session, [_commission(0, None, 3)], client_commission=None)
    uc._commission_repo.get = AsyncMock(return_value=_commission(0, None, 3))
    await uc.execute(_create_cmd(500, coupon_id=coupon.id))
    assert session.locks == ["User", "Coupon"]
    assert coupon.used_count == 1
    assert len([o for o in session.added if isinstance(o, CouponRedemption)]) == 1

    # Pending first transfer reserves the benefit for any other campaign.
    other = LedgerSession(coupon=_coupon(campaign_rules=_rules(segment="first_transfer")), pending=1)
    uc2, _, _ = _create_use_case(other, [_commission(0, None, 3)], client_commission=_commission(0, None, 3))
    with pytest.raises(ValueError, match="reservado"):
        await uc2.execute(_create_cmd(500, coupon_id=other.coupon.id))
    assert other.coupon.used_count == 0


# --------------------------------------------------------------------------- #
# Edición / borrado: orden de bloqueos, liberación exactamente una vez
# --------------------------------------------------------------------------- #
def _txn(status, *, coupon_id=None, user_id=None):
    return MagicMock(id=uuid4(), coupon_id=coupon_id, user_id=user_id or uuid4(), status=status,
                     checked=False, social_reason_bank_id=None, destinations=[])


def _update_uc(session, entity):
    repo = AsyncMock()
    repo.get = AsyncMock(return_value=entity)
    return UpdateTransactionUseCase(repo, AsyncMock(), AsyncMock(), AsyncMock(), session=session)


@pytest.mark.asyncio
async def test_failing_a_pending_coupon_operation_releases_exactly_once():
    coupon = _coupon(used_count=1)
    redemption = SimpleNamespace(deleted=False)
    entity = _txn(TransactionStatus.verification, coupon_id=coupon.id)
    session = LedgerSession(coupon=coupon, transaction=entity, owner=entity.user_id, redemptions=[redemption])
    uc = _update_uc(session, entity)

    await uc.execute(TransactionUpdateCmd(id=entity.id, status=TransactionStatus.failed))
    assert entity.status == TransactionStatus.failed and coupon.used_count == 0 and redemption.deleted
    assert session.locks == ["User", "Transaction", "Coupon"]

    # A later edit of the failed operation (or its deletion) never releases twice.
    await uc.execute(TransactionUpdateCmd(id=entity.id, observaciones="nota"))
    await DeleteTransactionUseCase(AsyncMock(), session).execute(entity.id)
    assert coupon.used_count == 0


@pytest.mark.asyncio
async def test_completed_operation_keeps_consumed_benefit_on_delete_and_edit():
    coupon = _coupon(used_count=1)
    redemption = SimpleNamespace(deleted=False)
    entity = _txn(TransactionStatus.completed, coupon_id=coupon.id)
    session = LedgerSession(coupon=coupon, transaction=entity, owner=entity.user_id, redemptions=[redemption])
    for change in [dict(status=TransactionStatus.failed), dict(user_id=uuid4())]:
        with pytest.raises(ValueError, match="completada"):
            await _update_uc(session, entity).execute(TransactionUpdateCmd(id=entity.id, **change))
    repo = AsyncMock()
    await DeleteTransactionUseCase(repo, session).execute(entity.id)
    repo.delete.assert_awaited_once()  # soft delete keeps history
    assert coupon.used_count == 1 and not redemption.deleted
    assert "Coupon" not in session.locks


@pytest.mark.asyncio
async def test_client_reassignment_locks_both_clients_in_stable_order():
    old_owner, new_owner = uuid4(), uuid4()
    entity = _txn(TransactionStatus.verification, user_id=old_owner)
    session = LedgerSession(transaction=entity, owner=old_owner)
    locked = []
    original = session.execute

    async def execute(stmt):
        if _entity_of(stmt) is User:
            locked.append(stmt.compile().params)
        return await original(stmt)

    session.execute = execute
    with pytest.raises(ValueError, match="destinations"):
        await _update_uc(session, entity).execute(TransactionUpdateCmd(id=entity.id, user_id=new_owner))
    ids = [next(iter(p.values())) for p in locked]
    assert ids == sorted([old_owner, new_owner], key=str)
    assert session.locks[:3] == ["User", "User", "Transaction"]


@pytest.mark.asyncio
async def test_concurrent_reassignment_is_detected_after_locking():
    entity = _txn(TransactionStatus.verification)
    session = LedgerSession(transaction=entity, owner=uuid4())  # owner changed before our lock
    with pytest.raises(ValueError, match="cambió de cliente"):
        await _update_uc(session, entity).execute(TransactionUpdateCmd(id=entity.id, observaciones="x"))
    with pytest.raises(ValueError, match="cambió de cliente"):
        await DeleteTransactionUseCase(AsyncMock(), session).execute(entity.id)


# --------------------------------------------------------------------------- #
# Rutas genéricas de cupones
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_generic_coupon_update_cannot_drop_quota_below_reserved_usages():
    entity = SimpleNamespace(id=uuid4(), coupon_type="STANDARD", campaign_rules=None, campaign_version=1,
                             used_count=5, max_uses=10, start_date=None, end_date=None)
    repo = AsyncMock()
    repo.get_for_update = AsyncMock(return_value=entity)
    with pytest.raises(ValueError, match="reservados/consumidos"):
        await UpdateCouponUseCase(repo).execute(CouponUpdateCmd(id=entity.id, max_uses=4))
    assert entity.max_uses == 10
    repo.commit.assert_not_called()


@pytest.mark.asyncio
async def test_generic_coupon_delete_cannot_remove_versioned_campaign():
    repo = AsyncMock()
    repo.get_for_update = AsyncMock(return_value=SimpleNamespace(coupon_type="CAMPAIGN"))
    with pytest.raises(ValueError, match="campañas"):
        await DeleteCouponUseCase(repo).execute(uuid4())
    repo.delete.assert_not_called()
    repo.get_for_update = AsyncMock(return_value=SimpleNamespace(coupon_type="STANDARD"))
    await DeleteCouponUseCase(repo).execute(uuid4())
    repo.delete.assert_awaited_once()


def test_discount_state_distinguishes_reserved_consumed_released():
    cid = uuid4()
    assert discount_state(None, TransactionStatus.completed) is None
    assert discount_state(cid, TransactionStatus.verification) == "reserved"
    assert discount_state(cid, TransactionStatus.verified) == "reserved"
    assert discount_state(cid, TransactionStatus.completed) == "consumed"
    assert discount_state(cid, TransactionStatus.failed) == "released"
    assert "coupon_discount_state" in TransactionReadDTO.model_computed_fields
