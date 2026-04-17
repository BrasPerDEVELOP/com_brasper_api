"""Tests para el endpoint POST /transactions/."""
import pytest
from uuid import uuid4

from app.modules.transactions.domain.enums import TransactionStatus


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

    monkeypatch.setattr(
        "app.modules.transactions.adapters.router.transaction_routes.save_transaction_voucher",
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
