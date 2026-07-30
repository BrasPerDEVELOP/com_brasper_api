from uuid import uuid4

from app.modules.transactions.application.schemas.bank_account_schema import (
    BankAccountCreateCmd,
)
from app.modules.transactions.application.schemas.transaction_schema import (
    BankAccountImportPayload,
)


def test_bank_account_identifiers_preserve_leading_zeroes_and_precision():
    cci = "01123200020106262661"
    account_number = "001102320201062626"

    command = BankAccountCreateCmd(
        user_id=uuid4(),
        bank_id=uuid4(),
        account_flow="destination",
        account_holder_type="naturalPerson",
        bank_country="pe",
        account_number=account_number,
        account_number_confirmation=account_number,
        cci_number=cci,
        cci_number_confirmation=cci,
    )

    assert command.account_number == account_number
    assert command.cci_number == cci


def test_legacy_numeric_identifiers_are_coerced_to_text():
    """Clientes previos a la migración 061 envían números; no deben recibir 422."""
    command = BankAccountCreateCmd(
        user_id=uuid4(),
        bank_id=uuid4(),
        account_flow="destination",
        account_holder_type="naturalPerson",
        bank_country="pe",
        document_number=12345678,
        account_number=1102320201062626,
    )

    assert command.document_number == "12345678"
    assert command.account_number == "1102320201062626"


def test_import_payload_accepts_numeric_document_number():
    """Las plantillas de importación traen el DNI como número de Excel."""
    payload = BankAccountImportPayload(
        bank_id=uuid4(),
        account_flow="origin",
        account_holder_type="naturalPerson",
        bank_country="pe",
        document_number=12345678,
    )

    assert payload.document_number == "12345678"
