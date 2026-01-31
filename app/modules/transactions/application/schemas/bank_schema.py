# app/modules/transactions/application/schemas/bank_schema.py
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.coin.domain.enums import Currency
from app.modules.transactions.domain.enums import BankCountry
from app.modules.transactions.domain.models import Bank


# Display string por moneda para la respuesta (ej. "Soles (PEN)")
CURRENCY_DISPLAY_BANK: dict[str, str] = {
    "pen": "Soles (PEN)",
    "usd": "Dólares (USD)",
    "brl": "Reales (BRL)",
}


class BankCreateCmd(BaseModel):
    bank: str
    account: Optional[str] = None
    pix: Optional[str] = None
    company: str
    currency: Currency
    image: str
    country: BankCountry


class BankUpdateCmd(BaseModel):
    id: UUID
    bank: Optional[str] = None
    account: Optional[str] = None
    pix: Optional[str] = None
    company: Optional[str] = None
    currency: Optional[Currency] = None
    image: Optional[str] = None
    country: Optional[BankCountry] = None


class BankReadDTO(BaseModel):
    id: UUID
    bank: str
    account: Optional[str] = None
    pix: Optional[str] = None
    company: str
    currency: Currency
    currency_display: str = ""
    image: str
    country: BankCountry

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
        )


class BankItemDTO(BaseModel):
    """Item de banco para la respuesta agrupada por país/moneda (sin id)."""
    bank: str
    account: Optional[str] = None
    pix: Optional[str] = None
    company: str
    currency: str
    image: str

    model_config = ConfigDict(from_attributes=True)


class BanksByCountryCurrencyDTO(BaseModel):
    """Estructura PE: { PEN: [...], USD: [...] }, BR: { BRL: [...] }."""
    pe: Optional[dict[str, list[BankItemDTO]]] = None
    br: Optional[dict[str, list[BankItemDTO]]] = None
