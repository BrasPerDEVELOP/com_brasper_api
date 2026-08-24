from datetime import datetime, timezone
from uuid import uuid4

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
