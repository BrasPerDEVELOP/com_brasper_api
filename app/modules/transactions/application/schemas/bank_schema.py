# app/modules/transactions/application/schemas/bank_schema.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.coin.domain.enums import Currency
from app.modules.transactions.domain.enums import BankCountry, SocialActor
from app.modules.transactions.domain.models import Bank


# Display string por moneda para la respuesta (ej. "Soles (PEN)")
CURRENCY_DISPLAY_BANK: dict[str, str] = {
    "pen": "Soles (PEN)",
    "usd": "Dólares (USD)",
    "brl": "Reales (BRL)",
}

# Mapeo inverso: display -> currency (para filtro por currency_display)
DISPLAY_TO_CURRENCY: dict[str, str] = {v: k for k, v in CURRENCY_DISPLAY_BANK.items()}


class BankCreateCmd(BaseModel):
    bank: str
    account: Optional[str] = None
    pix: Optional[str] = None
    company: str
    currency: Currency
    image: Optional[str] = None
    country: BankCountry
    social_actor: Optional[SocialActor] = None


class BankUpdateCmd(BaseModel):
    id: UUID
    bank: Optional[str] = None
    account: Optional[str] = None
    pix: Optional[str] = None
    company: Optional[str] = None
    currency: Optional[Currency] = None
    image: Optional[str] = None
    country: Optional[BankCountry] = None
    social_actor: Optional[SocialActor] = None


class BankReadDTO(BaseModel):
    id: UUID
    bank: str
    account: Optional[str] = None
    pix: Optional[str] = None
    company: str
    currency: Currency
    currency_display: str = ""
    image: Optional[str] = None
    country: BankCountry
    social_actor: Optional[SocialActor] = None
    created_at: datetime
    created_by: Optional[str] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_bank(cls, entity: Bank) -> "BankReadDTO":
        return cls(
            id=entity.id,
            bank=entity.bank,
            account=entity.account,
            pix=entity.pix,
            company=entity.company,
            currency=entity.currency,
            currency_display=CURRENCY_DISPLAY_BANK.get(entity.currency.value, entity.currency.value.upper()),
            image=entity.image,
            country=entity.country,
            social_actor=entity.social_actor,
            created_at=entity.created_at,
            created_by=entity.created_by,
            updated_at=entity.updated_at,
        )


class BankOptionDTO(BaseModel):
    """Item reducido para dropdowns/select: id, bank, currency, country."""
    id: UUID
    bank: str
    currency: Currency
    country: BankCountry

    model_config = ConfigDict(from_attributes=True)


class BankItemDTO(BaseModel):
    """Item de banco para la respuesta agrupada por país/moneda (sin id)."""
    bank: str
    account: Optional[str] = None
    pix: Optional[str] = None
    company: str
    currency: str
    image: Optional[str] = None
    social_actor: Optional[SocialActor] = None

    model_config = ConfigDict(from_attributes=True)


class BanksByCountryCurrencyDTO(BaseModel):
    """Estructura PE: { PEN: [...], USD: [...] }, BR: { BRL: [...] }."""
    pe: Optional[dict[str, list[BankItemDTO]]] = None
    br: Optional[dict[str, list[BankItemDTO]]] = None
