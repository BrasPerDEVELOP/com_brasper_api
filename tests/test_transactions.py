"""Tests para el endpoint POST /transactions/."""
import importlib

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.modules.coin.domain.enums import Currency
from app.modules.transactions.domain.enums import TransactionStatus
from app.modules.transactions.application.schemas.transaction_schema import (
    TransactionCreateCmd,
    TransactionUpdateCmd,
    TransactionReadDTO,
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

    uc = CreateTransactionUseCase(txn_repo, tax_rate_repo, user_repo, bank_account_repo)
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

    uc = CreateTransactionUseCase(txn_repo, tax_rate_repo, user_repo, bank_account_repo)
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

    monkeypatch.setattr(TransactionReadDTO, "model_validate", lambda obj: MagicMock())

    uc = UpdateTransactionUseCase(txn_repo, bank_account_repo)
    return uc, entity


@pytest.mark.asyncio
async def test_update_keeps_explicit_company_name_over_destination_snapshot(monkeypatch):
    """UpdateTransactionUseCase: la razón social enviada gana sobre el snapshot de la cuenta destino."""
    uc, entity = _build_update_uc(monkeypatch, dest_bank_company="Brasper 21 Corretora De Cambio Ltda")

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
    uc, entity = _build_update_uc(monkeypatch, dest_bank_company="Brasper 21 Corretora De Cambio Ltda")

    cmd = TransactionUpdateCmd(
        id=uuid4(),
        bank_account_destination=uuid4(),
    )
    await uc.execute(cmd)

    assert entity.company_name == "Brasper 21 Corretora De Cambio Ltda"


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
