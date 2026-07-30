# app/modules/transactions/application/schemas/bank_account_schema.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.transactions.domain.enums import BankCountry, AccountFlowType, SocialActor


# Los identificadores bancarios pasaron de BIGINT a texto (migración 061). Clientes
# antiguos siguen enviándolos como número JSON; se aceptan y se normalizan a str en
# lugar de responder 422. La salida siempre es texto.
LEGACY_NUMERIC_IDENTIFIERS = ConfigDict(coerce_numbers_to_str=True)


class BankAccountCreateCmd(BaseModel):
    model_config = LEGACY_NUMERIC_IDENTIFIERS

    user_id: UUID
    bank_id: UUID
    account_flow: AccountFlowType
    account_holder_type: SocialActor
    bank_country: BankCountry
    holder_names: Optional[str] = None
    holder_surnames: Optional[str] = None
    document_number: Optional[str] = None
    business_name: Optional[str] = None
    ruc_number: Optional[str] = None
    legal_representative_name: Optional[str] = None
    legal_representative_document: Optional[str] = None
    account_number: Optional[str] = None
    account_number_confirmation: Optional[str] = None
    cci_number: Optional[str] = None
    cci_number_confirmation: Optional[str] = None
    pix_key: Optional[str] = None
    pix_key_confirmation: Optional[str] = None
    pix_key_type: Optional[str] = None
    cpf: Optional[str] = None


class BankAccountUpdateCmd(BaseModel):
    model_config = LEGACY_NUMERIC_IDENTIFIERS

    id: UUID
    user_id: Optional[UUID] = None
    bank_id: Optional[UUID] = None
    account_flow: Optional[AccountFlowType] = None
    account_holder_type: Optional[SocialActor] = None
    bank_country: Optional[BankCountry] = None
    holder_names: Optional[str] = None
    holder_surnames: Optional[str] = None
    document_number: Optional[str] = None
    business_name: Optional[str] = None
    ruc_number: Optional[str] = None
    legal_representative_name: Optional[str] = None
    legal_representative_document: Optional[str] = None
    account_number: Optional[str] = None
    account_number_confirmation: Optional[str] = None
    cci_number: Optional[str] = None
    cci_number_confirmation: Optional[str] = None
    pix_key: Optional[str] = None
    pix_key_confirmation: Optional[str] = None
    pix_key_type: Optional[str] = None
    cpf: Optional[str] = None


class BankAccountReadDTO(BaseModel):
    id: UUID
    user_id: UUID
    bank_id: UUID
    account_flow: AccountFlowType
    account_holder_type: SocialActor
    bank_country: BankCountry
    holder_names: Optional[str] = None
    holder_surnames: Optional[str] = None
    document_number: Optional[str] = None
    business_name: Optional[str] = None
    ruc_number: Optional[str] = None
    legal_representative_name: Optional[str] = None
    legal_representative_document: Optional[str] = None
    account_number: Optional[str] = None
    cci_number: Optional[str] = None
    pix_key: Optional[str] = None
    pix_key_type: Optional[str] = None
    cpf: Optional[str] = None
    created_at: datetime
    created_by: Optional[str] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
