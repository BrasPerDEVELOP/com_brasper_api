"""Tests de concurrencia para la redención de cupones.

Objetivo: demostrar que, bajo redenciones CONCURRENTES del mismo cupón,
``CreateTransactionUseCase`` mantiene dos invariantes:

  (a) ``used_count`` nunca supera ``max_uses``;
  (b) un mismo usuario no excede ``per_user_limit``.

LIMITACIÓN DEL HARNESS (documentada): el proyecto no provee una base de datos
de pruebas ni una sesión async real (``tests/conftest.py`` usa AsyncMock +
``TestClient`` síncrono; ``vitest`` no aplica aquí). No es viable, por tanto,
ejercitar ``SELECT ... FOR UPDATE`` ni el índice único parcial de la migración
052 contra Postgres en CI.

Para reproducir la carrera de la forma más fiel posible se simula el bloqueo de
fila con un ``asyncio.Lock`` por cupón: la sesión adquiere el lock al ejecutar el
``select(Coupon).with_for_update()`` y lo libera en ``commit()``. Esto modela el
comportamiento de Postgres (la segunda transacción concurrente queda bloqueada
hasta que la primera confirma, y entonces observa el ``used_count`` ya
incrementado y la fila de ``CouponRedemption`` recién creada). Dos corrutinas
reales lanzadas con ``asyncio.gather`` compiten por ese lock, igual que dos
peticiones HTTP simultáneas competirían por la fila en la BD.

La lógica de servidor bajo prueba (``_apply_server_financials`` / ``execute``)
NO se modifica: estos tests la consumen tal cual.
"""
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.modules.coin.domain.enums import Currency
from app.modules.transactions.application.schemas.transaction_schema import (
    TransactionCreateCmd,
    TransactionReadDTO,
)
from app.modules.transactions.application.use_cases.transaction_use_cases import (
    CreateTransactionUseCase,
)
from app.modules.world_cup.models import CouponRedemption


# --------------------------------------------------------------------------- #
# Fakes que modelan la BD compartida entre "peticiones" concurrentes.
# --------------------------------------------------------------------------- #
class _Result:
    """Imita el objeto Result de SQLAlchemy para ``scalar_one_or_none``."""

    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class FakeCouponDB:
    """Estado compartido: un cupón con su lock de fila y la tabla de redenciones."""

    def __init__(self, coupon):
        self.coupon = coupon
        self.row_lock = asyncio.Lock()  # modela SELECT ... FOR UPDATE sobre la fila
        self.redemptions: list[CouponRedemption] = []


class FakeSession:
    """Sesión async por "petición". Comparte estado vía ``FakeCouponDB``.

    - ``execute(select(Coupon)...for_update)`` adquiere el lock de fila y
      devuelve el cupón compartido.
    - ``scalar(count CouponRedemption)`` cuenta filas vivas (deleted == False).
    - ``add`` agrega la redención al estado compartido.

    El lock se libera al cerrar la transacción: en producción esto ocurre tanto
    en commit como en rollback. Aquí ``commit()`` lo libera en el camino feliz y
    el test lo libera en un ``finally`` (vía ``_release``) cuando la corrutina
    termina por excepción de validación, replicando el rollback.
    """

    def __init__(self, db: FakeCouponDB, user_id):
        self._db = db
        self._user_id = user_id  # usuario de esta "petición" (cmd.user_id)
        self._holds_lock = False

    async def execute(self, _stmt):
        # En la lógica real solo hay un execute(select(Coupon)...for_update()).
        if not self._holds_lock:
            await self._db.row_lock.acquire()
            self._holds_lock = True
        return _Result(self._db.coupon)

    async def scalar(self, _stmt):
        # Réplica de: count(CouponRedemption) WHERE coupon_id == coupon.id
        # AND user_id == cmd.user_id AND deleted == False. El lock de fila ya
        # está tomado, por lo que esta lectura ve lo confirmado por la
        # transacción previa que liberó el lock.
        return sum(
            1
            for r in self._db.redemptions
            if not r.deleted
            and r.coupon_id == self._db.coupon.id
            and r.user_id == self._user_id
        )

    def add(self, obj):
        self._db.redemptions.append(obj)

    def _release(self):
        if self._holds_lock:
            self._db.row_lock.release()
            self._holds_lock = False


class FakeRepo:
    """Repositorio de transacciones; ``commit`` libera el lock de fila (fin de tx)."""

    def __init__(self, session: FakeSession, code: str):
        self._session = session
        self._code = code
        self.added: list = []

    async def add(self, entity):
        # Persiste la transacción y le asigna un id (como la BD).
        entity.id = uuid4()
        self.added.append(entity)
        return entity

    async def commit(self):
        # El incremento de used_count y la fila de redención se "confirman" aquí;
        # liberar el lock permite avanzar a la corrutina que espera la fila.
        self._session._release()

    async def refresh(self, entity, load_noload_relations=None):
        return entity

    async def next_sequential_transaction_code(self, coin_a, coin_b):
        return self._code


def _make_commission():
    c = MagicMock()
    c.coin_a = Currency.pen
    c.coin_b = Currency.brl
    c.min_amount = None
    c.max_amount = None
    c.percentage = 10  # 10% comisión
    return c


def _make_tax_rate():
    t = MagicMock()
    t.coin_a = Currency.pen
    t.coin_b = Currency.brl
    t.tax = 1  # tasa neutra para simplificar montos
    return t


def _make_coupon(*, max_uses, per_user_limit, discount_percentage=10.0):
    return SimpleNamespace(
        id=uuid4(),
        code="MUNDIAL-PER-BRA",
        is_active=True,
        lifecycle_status="ACTIVE",
        deleted=False,
        start_date=None,
        end_date=None,
        origin_currency=None,  # NULL == ALL
        destination_currency=None,
        discount_percentage=discount_percentage,
        max_uses=max_uses,
        per_user_limit=per_user_limit,
        used_count=0,
    )


def _make_use_case(db: FakeCouponDB, *, user_id, commission, tax_rate, code):
    session = FakeSession(db, user_id)
    repo = FakeRepo(session, code)

    user_repo = MagicMock()

    async def _list_ids_by_roles(_roles):
        return [uuid4()]

    user_repo.list_ids_by_roles = _list_ids_by_roles

    tax_rate_repo = MagicMock()

    async def _tax_get(_id):
        return tax_rate

    tax_rate_repo.get = _tax_get

    commission_repo = MagicMock()

    async def _commission_get(_id):
        return commission

    commission_repo.get = _commission_get

    # bank snapshot: cuenta destino con banco
    bank = MagicMock(bank="Banco X", company="Empresa Y")
    dest_acc = MagicMock(bank_id=uuid4(), bank=bank)
    bank_account_repo = MagicMock()

    async def _bank_get(_id, eager_options=None):
        return dest_acc

    bank_account_repo.get = _bank_get

    uc = CreateTransactionUseCase(
        repo=repo,
        tax_rate_repo=tax_rate_repo,
        user_repo=user_repo,
        bank_account_repo=bank_account_repo,
        commission_repo=commission_repo,
        session=session,
    )
    return uc, session


def _make_cmd(*, user_id, coupon_id):
    return TransactionCreateCmd(
        bank_account_destination=uuid4(),
        user_id=user_id,
        tax_rate_id=uuid4(),
        commission_id=uuid4(),
        coupon_id=coupon_id,
        origin_amount=100.0,
        destination_amount=100.0,
        code="",
    )


@pytest.fixture(autouse=True)
def _stub_read_dto(monkeypatch):
    """Evita validar el DTO de salida (no es el foco de estos tests)."""
    monkeypatch.setattr(TransactionReadDTO, "model_validate", lambda obj: MagicMock())


# --------------------------------------------------------------------------- #
# (a) used_count nunca supera max_uses bajo concurrencia.
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_concurrent_redemptions_never_exceed_max_uses():
    """5 redenciones concurrentes de distintos usuarios sobre un cupón con
    max_uses=3: exactamente 3 confirman y used_count termina en 3 (no en 5)."""
    coupon = _make_coupon(max_uses=3, per_user_limit=None)
    db = FakeCouponDB(coupon)
    commission = _make_commission()
    tax_rate = _make_tax_rate()

    async def attempt(i):
        uid = uuid4()
        uc, session = _make_use_case(db, user_id=uid, commission=commission, tax_rate=tax_rate, code=f"PxB-{i:03d}")
        cmd = _make_cmd(user_id=uid, coupon_id=coupon.id)
        try:
            await uc.execute(cmd)
            return True
        except ValueError:
            return False
        finally:
            session._release()  # rollback: libera la fila si execute() no llegó a commit

    results = await asyncio.gather(*(attempt(i) for i in range(5)))

    successes = sum(1 for r in results if r)
    assert successes == 3, f"esperaba 3 redenciones exitosas, hubo {successes}"
    assert coupon.used_count == 3, f"used_count={coupon.used_count} superó max_uses=3"
    assert coupon.used_count <= coupon.max_uses
    # Una fila de redención por éxito.
    assert len([r for r in db.redemptions if not r.deleted]) == 3


@pytest.mark.asyncio
async def test_concurrent_redemptions_at_exactly_max_uses_all_succeed():
    """Si #intentos == max_uses, todos confirman y used_count == max_uses."""
    coupon = _make_coupon(max_uses=4, per_user_limit=None)
    db = FakeCouponDB(coupon)
    commission = _make_commission()
    tax_rate = _make_tax_rate()

    async def attempt(i):
        uid = uuid4()
        uc, session = _make_use_case(db, user_id=uid, commission=commission, tax_rate=tax_rate, code=f"PxB-{i:03d}")
        cmd = _make_cmd(user_id=uid, coupon_id=coupon.id)
        try:
            await uc.execute(cmd)
            return True
        except ValueError:
            return False
        finally:
            session._release()

    results = await asyncio.gather(*(attempt(i) for i in range(4)))
    assert all(results)
    assert coupon.used_count == 4
    assert coupon.used_count <= coupon.max_uses


# --------------------------------------------------------------------------- #
# (b) un mismo usuario no excede per_user_limit bajo concurrencia.
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_concurrent_same_user_cannot_exceed_per_user_limit():
    """Mismo usuario, 4 redenciones concurrentes, per_user_limit=1 (max_uses alto):
    solo 1 confirma; las demás fallan con 'límite de uso'."""
    coupon = _make_coupon(max_uses=100, per_user_limit=1)
    db = FakeCouponDB(coupon)
    commission = _make_commission()
    tax_rate = _make_tax_rate()
    same_user = uuid4()

    async def attempt(i):
        uc, session = _make_use_case(db, user_id=same_user, commission=commission, tax_rate=tax_rate, code=f"PxB-{i:03d}")
        cmd = _make_cmd(user_id=same_user, coupon_id=coupon.id)
        try:
            await uc.execute(cmd)
            return True
        except ValueError:
            return False
        finally:
            session._release()

    results = await asyncio.gather(*(attempt(i) for i in range(4)))

    successes = sum(1 for r in results if r)
    assert successes == 1, f"esperaba 1 redención del mismo usuario, hubo {successes}"
    # used_count solo se incrementa cuando la redención efectivamente procede.
    assert coupon.used_count == 1
    live = [r for r in db.redemptions if not r.deleted and r.user_id == same_user]
    assert len(live) == 1, f"el usuario tiene {len(live)} redenciones vivas (límite=1)"


@pytest.mark.asyncio
async def test_concurrent_distinct_users_each_respect_per_user_limit():
    """Dos usuarios distintos, cada uno con 2 intentos concurrentes,
    per_user_limit=1: cada usuario confirma exactamente una vez (2 en total)."""
    coupon = _make_coupon(max_uses=100, per_user_limit=1)
    db = FakeCouponDB(coupon)
    commission = _make_commission()
    tax_rate = _make_tax_rate()
    user_a, user_b = uuid4(), uuid4()

    async def attempt(uid, i):
        uc, session = _make_use_case(db, user_id=uid, commission=commission, tax_rate=tax_rate, code=f"PxB-{i:03d}")
        cmd = _make_cmd(user_id=uid, coupon_id=coupon.id)
        try:
            await uc.execute(cmd)
            return uid
        except ValueError:
            return None
        finally:
            session._release()

    attempts = [attempt(user_a, 0), attempt(user_a, 1), attempt(user_b, 2), attempt(user_b, 3)]
    results = await asyncio.gather(*attempts)

    confirmed = [r for r in results if r is not None]
    assert sorted(map(str, confirmed)) == sorted([str(user_a), str(user_b)])
    assert coupon.used_count == 2
    for uid in (user_a, user_b):
        live = [r for r in db.redemptions if not r.deleted and r.user_id == uid]
        assert len(live) == 1
