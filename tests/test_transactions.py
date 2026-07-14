"""Tests para el endpoint POST /transactions/."""
import importlib
import json

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.modules.coin.domain.enums import Currency
from app.modules.transactions.domain.enums import AccountFlowType, TransactionStatus
from app.modules.transactions.application.schemas.transaction_schema import (
    TransactionCreateCmd,
    TransactionUpdateCmd,
    TransactionReadDTO,
    TransactionDestinationInput,
)
from app.modules.transactions.application.use_cases import transaction_use_cases
from app.modules.transactions.application.use_cases.transaction_use_cases import (
    CreateTransactionUseCase,
    UpdateTransactionUseCase,
)
from app.modules.users.domain.enums import UserRole


def test_post_transaction_json_creates_success(client, valid_transaction_payload):
    """POST /transactions/ con JSON retorna 201 y la transacción creada."""
    response = client.post(
        "/transactions/",
        json=valid_transaction_payload,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["code"] == valid_transaction_payload["code"]
    assert data["origin_amount"] == valid_transaction_payload["origin_amount"]
    assert data["destination_amount"] == valid_transaction_payload["destination_amount"]
    assert data["status"] == TransactionStatus.verification.value
    assert data["commission_result"] == valid_transaction_payload["commission_result"]
    assert data["total_to_send"] == valid_transaction_payload["total_to_send"]


def test_update_payload_strips_null_voucher_paths_without_remove_flags():
    """PUT: `null` en un voucher no borra al actualizar otra ruta (p. ej. reenviar GET + un campo)."""
    u = {
        "send_voucher": None,
        "payment_voucher": None,
        "checked_image": "transaction_vouchers/only_new.pdf",
    }
    transaction_use_cases._drop_null_voucher_paths_unless_remove(
        u, remove_send=False, remove_payment=False, remove_checked=False
    )
    assert "send_voucher" not in u
    assert "payment_voucher" not in u
    assert u["checked_image"] == "transaction_vouchers/only_new.pdf"


@pytest.mark.asyncio
async def test_resolve_agent_id_for_create_keeps_explicit():
    repo = AsyncMock()
    repo.list_ids_by_roles = AsyncMock()
    explicit = uuid4()
    got = await transaction_use_cases._resolve_agent_id_for_create(repo, explicit)
    assert got == explicit
    repo.list_ids_by_roles.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_agent_id_for_create_uses_pool_when_none():
    repo = AsyncMock()
    a, b = uuid4(), uuid4()
    repo.list_ids_by_roles = AsyncMock(return_value=[a, b])
    got = await transaction_use_cases._resolve_agent_id_for_create(repo, None)
    assert got in (a, b)
    repo.list_ids_by_roles.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_transaction_use_case_assigns_agent_from_admin_sales_pool(monkeypatch):
    """CreateTransactionUseCase: sin agent_id pide candidatos admin/sales y persiste uno de ellos."""
    assigned_id = uuid4()
    user_repo = AsyncMock()
    user_repo.list_ids_by_roles = AsyncMock(return_value=[assigned_id])

    tax = MagicMock()
    tax.coin_a = Currency.pen
    tax.coin_b = Currency.brl
    tax_rate_repo = AsyncMock()
    tax_rate_repo.get = AsyncMock(return_value=tax)

    captured: dict = {}

    async def capture_add(entity):
        captured["agent_id"] = entity.agent_id
        return entity

    txn_repo = AsyncMock()
    txn_repo.add = AsyncMock(side_effect=capture_add)
    txn_repo.commit = AsyncMock()
    txn_repo.refresh = AsyncMock()
    txn_repo.next_sequential_transaction_code = AsyncMock(return_value="PxB-TEST-001")

    monkeypatch.setattr(TransactionReadDTO, "model_validate", lambda obj: MagicMock())

    bank = MagicMock()
    bank.bank = "Banco X"
    bank.company = "Empresa Y"
    dest_acc = MagicMock()
    dest_acc.bank_id = uuid4()
    dest_acc.bank = bank
    bank_account_repo = AsyncMock()
    bank_account_repo.get = AsyncMock(return_value=dest_acc)
    bank_repo = AsyncMock()

    uc = CreateTransactionUseCase(
        txn_repo, tax_rate_repo, user_repo, bank_account_repo, bank_repo
    )
    cmd = TransactionCreateCmd(
        bank_account_destination=uuid4(),
        user_id=uuid4(),
        tax_rate_id=uuid4(),
        commission_id=uuid4(),
        origin_amount=1.0,
        destination_amount=1.0,
        code="",
    )
    await uc.execute(cmd)

    user_repo.list_ids_by_roles.assert_awaited_once()
    roles_arg = user_repo.list_ids_by_roles.await_args.args[0]
    assert tuple(roles_arg) == (UserRole.admin.value, UserRole.sales.value)
    assert captured["agent_id"] == assigned_id


@pytest.mark.asyncio
async def test_create_transaction_use_case_keeps_explicit_agent_id(monkeypatch):
    """CreateTransactionUseCase: con agent_id en el cmd no consulta el pool."""
    explicit = uuid4()
    user_repo = AsyncMock()
    user_repo.list_ids_by_roles = AsyncMock()

    tax = MagicMock()
    tax.coin_a = Currency.pen
    tax.coin_b = Currency.brl
    tax_rate_repo = AsyncMock()
    tax_rate_repo.get = AsyncMock(return_value=tax)

    captured: dict = {}

    async def capture_add(entity):
        captured["agent_id"] = entity.agent_id
        return entity

    txn_repo = AsyncMock()
    txn_repo.add = AsyncMock(side_effect=capture_add)
    txn_repo.commit = AsyncMock()
    txn_repo.refresh = AsyncMock()
    txn_repo.next_sequential_transaction_code = AsyncMock(return_value="PxB-TEST-002")

    monkeypatch.setattr(TransactionReadDTO, "model_validate", lambda obj: MagicMock())

    bank = MagicMock()
    bank.bank = "Banco X"
    bank.company = "Empresa Y"
    dest_acc = MagicMock()
    dest_acc.bank_id = uuid4()
    dest_acc.bank = bank
    bank_account_repo = AsyncMock()
    bank_account_repo.get = AsyncMock(return_value=dest_acc)
    bank_repo = AsyncMock()

    uc = CreateTransactionUseCase(
        txn_repo, tax_rate_repo, user_repo, bank_account_repo, bank_repo
    )
    cmd = TransactionCreateCmd(
        bank_account_destination=uuid4(),
        user_id=uuid4(),
        agent_id=explicit,
        tax_rate_id=uuid4(),
        commission_id=uuid4(),
        origin_amount=1.0,
        destination_amount=1.0,
        code="",
    )
    await uc.execute(cmd)

    user_repo.list_ids_by_roles.assert_not_called()
    assert captured["agent_id"] == explicit


@pytest.mark.asyncio
async def test_create_persists_exact_social_reason_bank_and_server_snapshots(monkeypatch):
    """La razón social usa su FK, sin reemplazar el banco de la cuenta destino."""
    user_repo = AsyncMock()
    user_repo.list_ids_by_roles = AsyncMock(return_value=[uuid4()])

    tax = MagicMock(coin_a=Currency.brl, coin_b=Currency.pen)
    tax_rate_repo = AsyncMock()
    tax_rate_repo.get = AsyncMock(return_value=tax)

    destination_bank_id = uuid4()
    destination_bank = MagicMock(
        bank="BCP",
        company="Empresa de cuenta destino",
    )
    destination_account = MagicMock(
        bank_id=destination_bank_id,
        bank=destination_bank,
    )
    bank_account_repo = AsyncMock()
    bank_account_repo.get = AsyncMock(return_value=destination_account)

    selected_social_reason_bank_id = uuid4()
    selected_social_reason_bank = MagicMock(
        bank="Santander",
        company="Brasper 21",
    )
    bank_repo = AsyncMock()
    bank_repo.get = AsyncMock(return_value=selected_social_reason_bank)

    captured: dict = {}

    async def capture_add(entity):
        captured["entity"] = entity
        return entity

    txn_repo = AsyncMock()
    txn_repo.add = AsyncMock(side_effect=capture_add)
    txn_repo.commit = AsyncMock()
    txn_repo.refresh = AsyncMock()
    txn_repo.next_sequential_transaction_code = AsyncMock(return_value="BxP-TEST-001")
    monkeypatch.setattr(TransactionReadDTO, "model_validate", lambda obj: MagicMock())

    uc = CreateTransactionUseCase(
        txn_repo,
        tax_rate_repo,
        user_repo,
        bank_account_repo,
        bank_repo,
    )
    cmd = TransactionCreateCmd(
        bank_account_destination=uuid4(),
        user_id=uuid4(),
        tax_rate_id=uuid4(),
        commission_id=uuid4(),
        social_reason_bank_id=selected_social_reason_bank_id,
        bank_name="Nombre manipulable que debe ignorarse",
        company_name="Empresa manipulable que debe ignorarse",
        origin_amount=1000.0,
        destination_amount=630.0,
    )

    await uc.execute(cmd)

    entity = captured["entity"]
    assert entity.bank_id == destination_bank_id
    assert entity.bank_name == "BCP"
    assert entity.social_reason_bank_id == selected_social_reason_bank_id
    assert entity.company_name == "Brasper 21"
    bank_repo.get.assert_awaited_once_with(selected_social_reason_bank_id)


@pytest.mark.asyncio
async def test_create_transaction_persists_special_calculator_discount(monkeypatch):
    """La calculadora especial (código ESPECIAL) persiste el descuento y el monto especial."""
    user_repo = AsyncMock()
    user_repo.list_ids_by_roles = AsyncMock(return_value=[uuid4()])

    tax = MagicMock()
    tax.coin_a = Currency.pen
    tax.coin_b = Currency.brl
    tax.tax = 1.494
    tax_rate_repo = AsyncMock()
    tax_rate_repo.get = AsyncMock(return_value=tax)

    commission = MagicMock()
    commission.percentage = 3
    commission.coin_a = Currency.pen
    commission.coin_b = Currency.brl
    commission.min_amount = 100
    commission.max_amount = 50_000
    commission_repo = AsyncMock()
    commission_repo.get = AsyncMock(return_value=commission)

    captured: dict = {}

    async def capture_add(entity):
        captured["commission_result"] = entity.commission_result
        captured["total_to_send"] = entity.total_to_send
        captured["destination_amount"] = entity.destination_amount
        captured["coupon_discount_code"] = entity.coupon_discount_code
        captured["coupon_discount_commission"] = entity.coupon_discount_commission
        captured["coupon_destination_amount"] = entity.coupon_destination_amount
        captured["coupon_discount_total_to_send"] = entity.coupon_discount_total_to_send
        return entity

    txn_repo = AsyncMock()
    txn_repo.add = AsyncMock(side_effect=capture_add)
    txn_repo.commit = AsyncMock()
    txn_repo.refresh = AsyncMock()
    txn_repo.next_sequential_transaction_code = AsyncMock(return_value="PxB-TEST-ESP")

    monkeypatch.setattr(TransactionReadDTO, "model_validate", lambda obj: MagicMock())

    bank = MagicMock()
    bank.bank = "Banco do Brasil - 001"
    bank.company = "Empresa Y"
    dest_acc = MagicMock()
    dest_acc.bank_id = uuid4()
    dest_acc.bank = bank
    bank_account_repo = AsyncMock()
    bank_account_repo.get = AsyncMock(return_value=dest_acc)
    bank_repo = AsyncMock()

    session = AsyncMock()

    uc = CreateTransactionUseCase(
        txn_repo,
        tax_rate_repo,
        user_repo,
        bank_account_repo,
        bank_repo,
        commission_repo,
        session,
    )
    cmd = TransactionCreateCmd(
        bank_account_destination=uuid4(),
        user_id=uuid4(),
        tax_rate_id=uuid4(),
        commission_id=uuid4(),
        origin_amount=1000.0,
        destination_amount=1450.0,
        code="",
        coupon_discount_code="ESPECIAL",
        coupon_discount_commission=0.55,
        coupon_discount_percentage=1.83,
    )
    await uc.execute(cmd)

    # base_commission = 1000 * 3% = 30; descuento especial 0.55 → comisión efectiva 29.45
    assert captured["commission_result"] == 29.45
    assert captured["total_to_send"] == 970.55
    # destino = 970.55 * 1.494 ≈ 1450 (con la comisión descontada, no la base 1449.18)
    assert captured["destination_amount"] == pytest.approx(1450.0, abs=0.01)
    # el descuento especial queda PERSISTIDO (antes se anulaba a None)
    assert captured["coupon_discount_code"] == "ESPECIAL"
    assert captured["coupon_discount_commission"] == 0.55
    assert captured["coupon_destination_amount"] == pytest.approx(1450.0, abs=0.01)
    assert captured["coupon_discount_total_to_send"] == 970.55


@pytest.mark.asyncio
async def test_special_calculator_uses_manual_tax_rate_instead_of_catalog():
    """ESPECIAL reproduce la tasa manual enviada por la calculadora."""
    commission = MagicMock(
        percentage=5,
        coin_a=Currency.pen,
        coin_b=Currency.brl,
        max_amount=50_000,
    )
    commission_repo = AsyncMock()
    commission_repo.get = AsyncMock(return_value=commission)
    use_case = CreateTransactionUseCase(
        AsyncMock(),
        AsyncMock(),
        AsyncMock(),
        AsyncMock(),
        AsyncMock(),
        commission_repo,
        AsyncMock(),
    )
    cmd = TransactionCreateCmd(
        bank_account_destination=uuid4(),
        user_id=uuid4(),
        tax_rate_id=uuid4(),
        commission_id=uuid4(),
        origin_amount=111,
        destination_amount=137.09,
        tax_amount=1.3,
        coupon_discount_code="ESPECIAL",
        coupon_discount_commission=0,
    )
    tax_rate = MagicMock(
        coin_a=Currency.pen,
        coin_b=Currency.brl,
        tax=1.483,
    )
    entity_data: dict = {}

    await use_case._apply_server_financials(cmd, tax_rate, entity_data)

    assert entity_data["commission_result"] == 5.55
    assert entity_data["total_to_send"] == 105.45
    assert entity_data["tax_amount"] == 1.3
    assert entity_data["destination_amount"] == 137.09


@pytest.mark.asyncio
async def test_normal_transaction_ignores_client_tax_rate_override():
    """Fuera de ESPECIAL, la tasa del catálogo continúa siendo autoritativa."""
    commission = MagicMock(
        percentage=5,
        coin_a=Currency.pen,
        coin_b=Currency.brl,
        max_amount=50_000,
    )
    commission_repo = AsyncMock()
    commission_repo.get = AsyncMock(return_value=commission)
    use_case = CreateTransactionUseCase(
        AsyncMock(),
        AsyncMock(),
        AsyncMock(),
        AsyncMock(),
        AsyncMock(),
        commission_repo,
        AsyncMock(),
    )
    cmd = TransactionCreateCmd(
        bank_account_destination=uuid4(),
        user_id=uuid4(),
        tax_rate_id=uuid4(),
        commission_id=uuid4(),
        origin_amount=111,
        destination_amount=156.38,
        tax_amount=1.3,
    )
    tax_rate = MagicMock(
        coin_a=Currency.pen,
        coin_b=Currency.brl,
        tax=1.483,
    )
    entity_data: dict = {}

    await use_case._apply_server_financials(cmd, tax_rate, entity_data)

    assert entity_data["tax_amount"] == 1.483
    assert entity_data["destination_amount"] == 156.38


def test_post_transaction_json_minimal_payload(client):
    """POST /transactions/ con payload mínimo (campos requeridos) retorna 201."""
    payload = {
        "bank_account_origin": str(uuid4()),
        "bank_account_destination": str(uuid4()),
        "user_id": str(uuid4()),
        "tax_rate_id": str(uuid4()),
        "commission_id": str(uuid4()),
        "origin_amount": 50.0,
        "destination_amount": 48.0,
        "code": "MIN-001",
    }
    response = client.post("/transactions/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "code" in data


def test_post_transaction_json_accepts_social_reason_bank_id(
    client, mock_create_transaction_uc, valid_transaction_payload
):
    selected_id = uuid4()
    response = client.post(
        "/transactions/",
        json={
            **valid_transaction_payload,
            "social_reason_bank_id": str(selected_id),
        },
    )

    assert response.status_code == 201
    cmd = mock_create_transaction_uc.execute.await_args.args[0]
    assert cmd.social_reason_bank_id == selected_id


def test_post_transaction_multipart_accepts_social_reason_bank_id(
    client, mock_create_transaction_uc, monkeypatch
):
    async def fake_save_transaction_voucher(file, prefix):
        return f"transaction_vouchers/{prefix}_new.jpeg"

    transaction_routes = importlib.import_module(
        "app.modules.transactions.adapters.router.transaction_routes"
    )
    monkeypatch.setattr(
        transaction_routes,
        "save_transaction_voucher",
        fake_save_transaction_voucher,
    )
    selected_id = uuid4()
    response = client.post(
        "/transactions/",
        data={
            "bank_account_destination": str(uuid4()),
            "user_id": str(uuid4()),
            "tax_rate_id": str(uuid4()),
            "commission_id": str(uuid4()),
            "social_reason_bank_id": str(selected_id),
            "origin_amount": "1000",
            "destination_amount": "630",
        },
        files={"send_voucher": ("send.jpeg", b"fake-image", "image/jpeg")},
    )

    assert response.status_code == 201
    cmd = mock_create_transaction_uc.execute.await_args.args[0]
    assert cmd.social_reason_bank_id == selected_id


def test_post_transaction_json_invalid_uuid_returns_error(client):
    """POST /transactions/ con UUID inválido retorna 400 o 422."""
    payload = {
        "bank_account_origin": "not-a-uuid",
        "bank_account_destination": str(uuid4()),
        "user_id": str(uuid4()),
        "tax_rate_id": str(uuid4()),
        "commission_id": str(uuid4()),
        "origin_amount": 100.0,
        "destination_amount": 95.0,
        "code": "TEST-001",
    }
    response = client.post("/transactions/", json=payload)
    assert response.status_code in (400, 422)


def test_post_transaction_json_missing_required_returns_error(client):
    """POST /transactions/ sin campos requeridos retorna 400 o 422."""
    payload = {
        "bank_account_origin": str(uuid4()),
        "bank_account_destination": str(uuid4()),
        # falta user_id, tax_rate_id, commission_id, origin_amount, destination_amount, code
    }
    response = client.post("/transactions/", json=payload)
    assert response.status_code in (400, 422)


def test_put_transaction_multipart_replacing_one_voucher_preserves_omitted_one(
    client, mock_update_transaction_uc, monkeypatch
):
    """PUT /transactions/ acepta File + path existente sin 500 y conserva el voucher omitido."""

    async def fake_save_transaction_voucher(file, prefix):
        return f"transaction_vouchers/{prefix}_new.jpeg"

    transaction_routes = importlib.import_module(
        "app.modules.transactions.adapters.router.transaction_routes"
    )
    monkeypatch.setattr(
        transaction_routes,
        "save_transaction_voucher",
        fake_save_transaction_voucher,
    )

    response = client.put(
        "/transactions/",
        data={
            "id": str(uuid4()),
            "payment_voucher": "transaction_vouchers/payment_existing.jpeg",
        },
        files={
            "send_voucher": ("send.jpeg", b"fake-image", "image/jpeg"),
        },
    )

    assert response.status_code == 200
    cmd = mock_update_transaction_uc.execute.await_args.args[0]
    updates = cmd.model_dump(exclude_unset=True)

    assert updates["send_voucher"] == "transaction_vouchers/send_new.jpeg"
    assert "payment_voucher" not in updates


def test_put_transaction_json_remove_payment_voucher_sets_explicit_flag(
    client, mock_update_transaction_uc
):
    """PUT /transactions/ permite borrar payment_voucher de forma explícita."""
    response = client.put(
        "/transactions/",
        json={
            "id": str(uuid4()),
            "remove_payment_voucher": True,
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    cmd = mock_update_transaction_uc.execute.await_args.args[0]
    updates = cmd.model_dump(exclude_unset=True)

    assert updates["remove_payment_voucher"] is True
    assert "payment_voucher" not in updates


def test_put_transaction_json_accepts_operation_number_alias(
    client, mock_update_transaction_uc
):
    """PUT /transactions/ acepta numero_operacion y lo normaliza a operation_number."""
    response = client.put(
        "/transactions/",
        json={
            "id": str(uuid4()),
            "numero_operacion": "OP-778899",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    cmd = mock_update_transaction_uc.execute.await_args.args[0]
    updates = cmd.model_dump(exclude_unset=True)

    assert updates["operation_number"] == "OP-778899"


def _build_update_uc(monkeypatch, dest_bank_company: str):
    """Arma UpdateTransactionUseCase con repos mockeados; retorna (uc, entity, cmd_dest_id)."""
    entity = MagicMock()
    entity.checked = False  # corta sync_transaction_status_from_checklist antes de leer vouchers
    entity.status = TransactionStatus.verification
    entity.social_reason_bank_id = None
    entity.bank_account_destination_id = uuid4()

    txn_repo = AsyncMock()
    txn_repo.get = AsyncMock(return_value=entity)
    txn_repo.update = AsyncMock()
    txn_repo.commit = AsyncMock()
    txn_repo.refresh = AsyncMock()

    bank = MagicMock()
    bank.bank = "Banco do Brasil - 001"
    bank.company = dest_bank_company
    dest_acc = MagicMock()
    dest_acc.bank_id = uuid4()
    dest_acc.bank = bank
    bank_account_repo = AsyncMock()
    bank_account_repo.get = AsyncMock(return_value=dest_acc)
    bank_repo = AsyncMock()

    monkeypatch.setattr(TransactionReadDTO, "model_validate", lambda obj: MagicMock())

    tax_rate_repo = AsyncMock()
    uc = UpdateTransactionUseCase(
        txn_repo, bank_account_repo, bank_repo, tax_rate_repo
    )
    return uc, entity, bank_repo


@pytest.mark.asyncio
async def test_multiple_destinations_validate_owner_currency_and_total():
    user_id = uuid4()
    first_id, second_id = uuid4(), uuid4()
    bank = MagicMock(currency=Currency.pen)
    accounts = {
        first_id: MagicMock(
            user_id=user_id,
            account_flow=AccountFlowType.destination,
            bank=bank,
        ),
        second_id: MagicMock(
            user_id=user_id,
            account_flow=AccountFlowType.destination,
            bank=bank,
        ),
    }
    bank_account_repo = AsyncMock()
    bank_account_repo.get = AsyncMock(side_effect=lambda account_id, **_: accounts[account_id])

    result = await transaction_use_cases._build_transaction_destinations(
        bank_account_repo,
        destinations=[
            TransactionDestinationInput(bank_account_id=first_id, amount=300),
            TransactionDestinationInput(bank_account_id=second_id, amount=330),
        ],
        user_id=user_id,
        destination_currency=Currency.pen,
        destination_amount=630,
    )

    assert [item.bank_account_id for item in result] == [first_id, second_id]
    assert [float(item.amount) for item in result] == [300, 330]


@pytest.mark.asyncio
async def test_multiple_destinations_reject_wrong_owner():
    account = MagicMock(
        user_id=uuid4(),
        account_flow=AccountFlowType.destination,
        bank=MagicMock(currency=Currency.pen),
    )
    bank_account_repo = AsyncMock()
    bank_account_repo.get = AsyncMock(return_value=account)

    with pytest.raises(ValueError, match="pertenecer al cliente"):
        await transaction_use_cases._build_transaction_destinations(
            bank_account_repo,
            destinations=[
                TransactionDestinationInput(bank_account_id=uuid4(), amount=10),
            ],
            user_id=uuid4(),
            destination_currency=Currency.pen,
            destination_amount=10,
        )


@pytest.mark.asyncio
async def test_multiple_destinations_reject_total_mismatch():
    user_id = uuid4()
    account = MagicMock(
        user_id=user_id,
        account_flow=AccountFlowType.destination,
        bank=MagicMock(currency=Currency.pen),
    )
    bank_account_repo = AsyncMock()
    bank_account_repo.get = AsyncMock(return_value=account)

    with pytest.raises(ValueError, match="suma de cuentas destino"):
        await transaction_use_cases._build_transaction_destinations(
            bank_account_repo,
            destinations=[
                TransactionDestinationInput(bank_account_id=uuid4(), amount=9),
            ],
            user_id=user_id,
            destination_currency=Currency.pen,
            destination_amount=10,
        )


@pytest.mark.asyncio
async def test_multiple_destinations_accept_one_cent_rounding_difference():
    user_id = uuid4()
    account = MagicMock(
        user_id=user_id,
        account_flow=AccountFlowType.destination,
        bank=MagicMock(currency=Currency.brl),
    )
    bank_account_repo = AsyncMock()
    bank_account_repo.get = AsyncMock(return_value=account)

    result = await transaction_use_cases._build_transaction_destinations(
        bank_account_repo,
        destinations=[
            TransactionDestinationInput(bank_account_id=uuid4(), amount=13.30),
        ],
        user_id=user_id,
        destination_currency=Currency.brl,
        destination_amount=13.29,
    )

    assert float(result[0].amount) == 13.30


@pytest.mark.asyncio
async def test_create_transaction_persists_multiple_destinations(monkeypatch):
    user_id = uuid4()
    first_id, second_id = uuid4(), uuid4()
    tax = MagicMock(coin_a=Currency.brl, coin_b=Currency.pen)
    tax_rate_repo = AsyncMock()
    tax_rate_repo.get = AsyncMock(return_value=tax)
    user_repo = AsyncMock()
    user_repo.list_ids_by_roles = AsyncMock(return_value=[uuid4()])

    first_bank = MagicMock(id=uuid4(), bank="BCP", company="Cliente", currency=Currency.pen)
    second_bank = MagicMock(id=uuid4(), bank="Interbank", company="Cliente", currency=Currency.pen)
    accounts = {
        first_id: MagicMock(
            user_id=user_id,
            bank_id=first_bank.id,
            bank=first_bank,
            account_flow=AccountFlowType.destination,
        ),
        second_id: MagicMock(
            user_id=user_id,
            bank_id=second_bank.id,
            bank=second_bank,
            account_flow=AccountFlowType.destination,
        ),
    }
    bank_account_repo = AsyncMock()
    bank_account_repo.get = AsyncMock(side_effect=lambda account_id, **_: accounts[account_id])
    captured = {}
    transaction_repo = AsyncMock()
    transaction_repo.add = AsyncMock(side_effect=lambda entity: captured.setdefault("entity", entity))
    transaction_repo.next_sequential_transaction_code = AsyncMock(return_value="BxP-TEST-MULTI")
    monkeypatch.setattr(TransactionReadDTO, "model_validate", lambda obj: MagicMock())

    use_case = CreateTransactionUseCase(
        transaction_repo,
        tax_rate_repo,
        user_repo,
        bank_account_repo,
        AsyncMock(),
    )
    await use_case.execute(TransactionCreateCmd(
        bank_account_destination=first_id,
        destinations=[
            TransactionDestinationInput(bank_account_id=first_id, amount=300),
            TransactionDestinationInput(bank_account_id=second_id, amount=330),
        ],
        user_id=user_id,
        tax_rate_id=uuid4(),
        commission_id=uuid4(),
        origin_amount=1000,
        destination_amount=629.99,
    ))

    entity = captured["entity"]
    assert entity.bank_account_destination_id == first_id
    assert float(entity.destination_amount) == 630
    assert [(item.bank_account_id, float(item.amount)) for item in entity.destinations] == [
        (first_id, 300),
        (second_id, 330),
    ]


def test_create_multipart_parses_destinations_json():
    first_id, second_id = uuid4(), uuid4()
    cmd, *_ = TransactionCreateCmd.from_form_data({
        "bank_account_destination": str(first_id),
        "destinations": json.dumps([
            {"bank_account_id": str(first_id), "amount": 300},
            {"bank_account_id": str(second_id), "amount": 330},
        ]),
        "user_id": str(uuid4()),
        "tax_rate_id": str(uuid4()),
        "commission_id": str(uuid4()),
        "origin_amount": "1000",
        "destination_amount": "630",
    })

    assert cmd.destinations is not None
    assert [item.bank_account_id for item in cmd.destinations] == [first_id, second_id]


@pytest.mark.asyncio
async def test_update_transaction_replaces_multiple_destinations(monkeypatch):
    user_id = uuid4()
    first_id, second_id = uuid4(), uuid4()
    tax_rate_id = uuid4()
    entity = MagicMock(
        checked=False,
        status=TransactionStatus.verification,
        social_reason_bank_id=None,
        bank_account_destination_id=first_id,
        user_id=user_id,
        tax_rate_id=tax_rate_id,
        destination_amount=630,
        destinations=[],
    )
    banks = {
        first_id: MagicMock(
            user_id=user_id,
            bank_id=uuid4(),
            bank=MagicMock(bank="BCP", company="Cliente", currency=Currency.pen),
            account_flow=AccountFlowType.destination,
        ),
        second_id: MagicMock(
            user_id=user_id,
            bank_id=uuid4(),
            bank=MagicMock(bank="Interbank", company="Cliente", currency=Currency.pen),
            account_flow=AccountFlowType.destination,
        ),
    }
    transaction_repo = AsyncMock()
    transaction_repo.get = AsyncMock(return_value=entity)
    bank_account_repo = AsyncMock()
    bank_account_repo.get = AsyncMock(side_effect=lambda account_id, **_: banks[account_id])
    tax_rate_repo = AsyncMock()
    tax_rate_repo.get = AsyncMock(return_value=MagicMock(coin_b=Currency.pen))
    monkeypatch.setattr(TransactionReadDTO, "model_validate", lambda obj: MagicMock())

    use_case = UpdateTransactionUseCase(
        transaction_repo,
        bank_account_repo,
        AsyncMock(),
        tax_rate_repo,
    )
    await use_case.execute(TransactionUpdateCmd(
        id=uuid4(),
        bank_account_destination=first_id,
        destination_amount=630,
        destinations=[
            TransactionDestinationInput(bank_account_id=first_id, amount=300),
            TransactionDestinationInput(bank_account_id=second_id, amount=330),
        ],
    ))

    assert [(item.bank_account_id, float(item.amount)) for item in entity.destinations] == [
        (first_id, 300),
        (second_id, 330),
    ]


@pytest.mark.asyncio
async def test_update_keeps_explicit_company_name_over_destination_snapshot(monkeypatch):
    """UpdateTransactionUseCase: la razón social enviada gana sobre el snapshot de la cuenta destino."""
    uc, entity, _ = _build_update_uc(
        monkeypatch, dest_bank_company="Brasper 21 Corretora De Cambio Ltda"
    )

    cmd = TransactionUpdateCmd(
        id=uuid4(),
        bank_account_destination=uuid4(),  # el front reenvía la cuenta destino aunque no cambie
        company_name="INGENITECH S.A.C",
    )
    await uc.execute(cmd)

    assert entity.company_name == "INGENITECH S.A.C"


@pytest.mark.asyncio
async def test_update_derives_company_name_from_destination_when_absent(monkeypatch):
    """UpdateTransactionUseCase: sin company_name explícito, se deriva del banco de la cuenta destino."""
    uc, entity, _ = _build_update_uc(
        monkeypatch, dest_bank_company="Brasper 21 Corretora De Cambio Ltda"
    )

    cmd = TransactionUpdateCmd(
        id=uuid4(),
        bank_account_destination=uuid4(),
    )
    await uc.execute(cmd)

    assert entity.company_name == "Brasper 21 Corretora De Cambio Ltda"


@pytest.mark.asyncio
async def test_update_persists_exact_social_reason_bank_and_derives_company(monkeypatch):
    uc, entity, bank_repo = _build_update_uc(
        monkeypatch, dest_bank_company="Empresa de cuenta destino"
    )
    selected_id = uuid4()
    bank_repo.get = AsyncMock(
        return_value=MagicMock(bank="Santander", company="Brasper 21")
    )

    cmd = TransactionUpdateCmd(
        id=uuid4(),
        bank_account_destination=uuid4(),
        social_reason_bank_id=selected_id,
        company_name="Nombre incorrecto enviado por el cliente",
    )
    await uc.execute(cmd)

    assert entity.social_reason_bank_id == selected_id
    assert entity.company_name == "Brasper 21"
    assert entity.bank_name == "Banco do Brasil - 001"
    bank_repo.get.assert_awaited_once_with(selected_id)


@pytest.mark.asyncio
async def test_update_rejects_nonexistent_social_reason_bank(monkeypatch):
    uc, _, bank_repo = _build_update_uc(
        monkeypatch, dest_bank_company="Empresa de cuenta destino"
    )
    selected_id = uuid4()
    bank_repo.get = AsyncMock(return_value=None)

    with pytest.raises(
        ValueError,
        match=f"No existe banco de razón social con id {selected_id}",
    ):
        await uc.execute(
            TransactionUpdateCmd(
                id=uuid4(),
                social_reason_bank_id=selected_id,
            )
        )


@pytest.mark.asyncio
async def test_update_clear_social_reason_restores_destination_company(monkeypatch):
    uc, entity, _ = _build_update_uc(
        monkeypatch, dest_bank_company="Empresa de cuenta destino"
    )
    entity.social_reason_bank_id = uuid4()

    await uc.execute(
        TransactionUpdateCmd(
            id=uuid4(),
            social_reason_bank_id=None,
        )
    )

    assert entity.social_reason_bank_id is None
    assert entity.company_name == "Empresa de cuenta destino"


@pytest.mark.asyncio
async def test_update_existing_social_reason_id_wins_over_legacy_company_name(monkeypatch):
    uc, entity, bank_repo = _build_update_uc(
        monkeypatch, dest_bank_company="Empresa de cuenta destino"
    )
    selected_id = uuid4()
    entity.social_reason_bank_id = selected_id
    bank_repo.get = AsyncMock(
        return_value=MagicMock(bank="Santander", company="Brasper 21")
    )

    await uc.execute(
        TransactionUpdateCmd(
            id=uuid4(),
            company_name="PicPay sobrescrito por un cliente antiguo",
        )
    )

    assert entity.social_reason_bank_id == selected_id
    assert entity.company_name == "Brasper 21"


def test_put_transaction_json_accepts_social_reason_bank_id(
    client, mock_update_transaction_uc
):
    selected_id = uuid4()
    response = client.put(
        "/transactions/",
        json={
            "id": str(uuid4()),
            "social_reason_bank_id": str(selected_id),
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    cmd = mock_update_transaction_uc.execute.await_args.args[0]
    assert cmd.social_reason_bank_id == selected_id


def test_put_transaction_multipart_accepts_social_reason_bank_id(
    client, mock_update_transaction_uc, monkeypatch
):
    async def fake_save_transaction_voucher(file, prefix):
        return f"transaction_vouchers/{prefix}_new.jpeg"

    transaction_routes = importlib.import_module(
        "app.modules.transactions.adapters.router.transaction_routes"
    )
    monkeypatch.setattr(
        transaction_routes,
        "save_transaction_voucher",
        fake_save_transaction_voucher,
    )
    selected_id = uuid4()
    response = client.put(
        "/transactions/",
        data={
            "id": str(uuid4()),
            "social_reason_bank_id": str(selected_id),
        },
        files={"send_voucher": ("send.jpeg", b"fake-image", "image/jpeg")},
    )

    assert response.status_code == 200
    cmd = mock_update_transaction_uc.execute.await_args.args[0]
    assert cmd.social_reason_bank_id == selected_id


def test_put_transaction_json_accepts_company_name(client, mock_update_transaction_uc):
    """PUT /transactions/ (JSON) parsea company_name en el cmd de actualización."""
    response = client.put(
        "/transactions/",
        json={
            "id": str(uuid4()),
            "company_name": "INGENITECH S.A.C",
        },
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    cmd = mock_update_transaction_uc.execute.await_args.args[0]
    updates = cmd.model_dump(exclude_unset=True)
    assert updates["company_name"] == "INGENITECH S.A.C"


def test_put_transaction_multipart_accepts_company_name(
    client, mock_update_transaction_uc, monkeypatch
):
    """PUT /transactions/ (multipart, al subir comprobante) parsea company_name."""

    async def fake_save_transaction_voucher(file, prefix):
        return f"transaction_vouchers/{prefix}_new.jpeg"

    transaction_routes = importlib.import_module(
        "app.modules.transactions.adapters.router.transaction_routes"
    )
    monkeypatch.setattr(
        transaction_routes,
        "save_transaction_voucher",
        fake_save_transaction_voucher,
    )

    response = client.put(
        "/transactions/",
        data={
            "id": str(uuid4()),
            "company_name": "INGENITECH S.A.C",
        },
        files={
            "send_voucher": ("send.jpeg", b"fake-image", "image/jpeg"),
        },
    )

    assert response.status_code == 200
    cmd = mock_update_transaction_uc.execute.await_args.args[0]
    updates = cmd.model_dump(exclude_unset=True)
    assert updates["company_name"] == "INGENITECH S.A.C"


def test_put_transaction_multipart_accepts_pdf_checked_image(
    client, mock_update_transaction_uc, monkeypatch
):
    """PUT /transactions/ acepta checked_image como documento PDF."""

    async def fake_save_transaction_voucher(file, prefix):
        return f"transaction_vouchers/{prefix}_new.pdf"

    transaction_routes = importlib.import_module(
        "app.modules.transactions.adapters.router.transaction_routes"
    )
    monkeypatch.setattr(
        transaction_routes,
        "save_transaction_voucher",
        fake_save_transaction_voucher,
    )

    response = client.put(
        "/transactions/",
        data={
            "id": str(uuid4()),
        },
        files={
            "checked_image": ("checklist.pdf", b"%PDF-1.4 fake", "application/pdf"),
        },
    )

    assert response.status_code == 200
    cmd = mock_update_transaction_uc.execute.await_args.args[0]
    updates = cmd.model_dump(exclude_unset=True)

    assert updates["checked_image"] == "transaction_vouchers/checked_new.pdf"
