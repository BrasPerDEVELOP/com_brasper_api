"""Contratos privados entre com_brasper_api y el bot Brasper."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.modules.users.domain.enums import DocumentType, PhoneCode


class AIClientDTO(BaseModel):
    id: UUID
    names: Optional[str] = None
    lastnames: Optional[str] = None
    code_phone: Optional[str] = None
    phone: Optional[str] = None
    document_type: Optional[str] = None
    document_verified: bool = False
    is_first_transfer: bool


class AIClientLookupDTO(BaseModel):
    found: bool
    ambiguous: bool = False
    client: Optional[AIClientDTO] = None


class AIClientUpsertCmd(BaseModel):
    names: str = Field(min_length=2, max_length=100)
    lastnames: str = Field(min_length=2, max_length=100)
    document_type: DocumentType
    document_number: str = Field(min_length=3, max_length=40)
    code_phone: PhoneCode
    phone: int = Field(gt=0, le=999_999_999_999_999)
    email: Optional[EmailStr] = None

    @model_validator(mode="after")
    def strip_identity(self):
        self.names = " ".join(self.names.split())
        self.lastnames = " ".join(self.lastnames.split())
        self.document_number = self.document_number.strip()
        return self


class AIClientUpsertDTO(BaseModel):
    id: UUID
    created: bool
    is_first_transfer: bool


class AIDepositAccountDTO(BaseModel):
    id: UUID
    currency: str
    country: str
    bank: str
    company: str
    account: Optional[str] = None
    pix: Optional[str] = None


class AIDepositAccountsDTO(BaseModel):
    data: list[AIDepositAccountDTO]
