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
