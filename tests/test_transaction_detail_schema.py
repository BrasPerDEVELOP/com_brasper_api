from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.modules.transactions.application.schemas import (
    TransactionDetailDTO,
    TransactionReadDTO,
)


def _transaction_payload() -> dict:
    transaction_id = uuid4()
    user_id = uuid4()
    destination_account_id = uuid4()
    now = datetime.now(timezone.utc)
    return {
        "id": transaction_id,
        "bank_account_destination_id": destination_account_id,
        "destinations": [
            {
                "id": uuid4(),
                "bank_account_id": destination_account_id,
                "amount": 21_345,
                "position": 0,
                "bank_account": {
                    "id": destination_account_id,
                    "bank_id": uuid4(),
                    "account_holder_type": "legalEntity",
                    "bank_country": "br",
                    "business_name": "ACME LTDA",
                    "ruc_number": "12345678000199",
                    "account_number": "0001-9",
                    "pix_key": "financeiro@acme.com",
                    "bank": {"bank": "Nubank", "currency": "BRL"},
                },
            }
        ],
        "user_id": user_id,
        "tax_rate_id": uuid4(),
        "commission_id": uuid4(),
        "status": "completed",
        "origin_amount": 14_956,
        "destination_amount": 21_345,
        "code": "PxB-00502",
        "created_at": now,
        "updated_at": now,
    }


def test_transaction_detail_exposes_destination_account_snapshot() -> None:
    detail = TransactionDetailDTO.model_validate(_transaction_payload())

    account = detail.destinations[0].bank_account
    assert account is not None
    assert account.bank_name == "Nubank"
    assert account.bank_currency == "BRL"
    assert account.account_number == "0001-9"
    assert account.pix_key == "financeiro@acme.com"
    assert account.business_name == "ACME LTDA"


def test_transaction_list_dto_keeps_destination_account_private() -> None:
    compact = TransactionReadDTO.model_validate(_transaction_payload())

    destination = compact.destinations[0].model_dump()
    assert "bank_account" not in destination


@pytest.mark.parametrize("dto", [TransactionReadDTO, TransactionDetailDTO])
def test_transaction_responses_serialize_user_documents(dto) -> None:
    payload = _transaction_payload()
    payload["user"] = {
        "id": payload["user_id"],
        "document_type": " CPF ",
        "document_number": " 00123456789 ",
    }
    user = dto.model_validate(payload).model_dump(mode="json")["user"]
    assert user["id"] == str(payload["user_id"])
    assert user["document_type"] == "CPF"
    assert user["document_number"] == "00123456789"


def test_transaction_orm_uses_related_users_primary_identification() -> None:
    from app.modules.transactions.domain.models import Transaction
    from app.modules.users.domain.models import User, UserIdentification

    payload = _transaction_payload()
    payload.pop("destinations")
    transaction = Transaction(**payload, checked=False)
    transaction.user = User(
        id=payload["user_id"],
        document_type=None,
        document_number=None,
        identifications=[
            UserIdentification(document_type="DNI", document_number="12345678", is_primary=False),
            UserIdentification(document_type="CPF", document_number="00123456789", is_primary=True),
        ],
    )
    for dto in (TransactionReadDTO, TransactionDetailDTO):
        user = dto.model_validate(transaction).model_dump(mode="json")["user"]
        assert user["document_type"] == "CPF"
        assert user["document_number"] == "00123456789"


def test_transaction_missing_document_serializes_explicit_nulls() -> None:
    user = TransactionReadDTO.model_validate(_transaction_payload()).model_dump()["user"]
    assert user["document_type"] is None
    assert user["document_number"] is None
