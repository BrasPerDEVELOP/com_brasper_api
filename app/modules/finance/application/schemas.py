# app/modules/finance/application/schemas.py
"""Schemas de tasas mensuales y egresos (contrato snake_case del backoffice)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.coin.domain.enums import Currency


class FxMonthRateDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    year: int
    month: int
    currency: Currency
    rate_to_pen: float
    updated_at: Optional[datetime] = None


class FxMonthRateUpsertCmd(BaseModel):
    """Una tasa; ``PUT /finance/fx-rates`` recibe una lista y hace upsert."""

    year: int = Field(ge=2015, le=2100)
    month: int = Field(ge=1, le=12)
    currency: Currency
    rate_to_pen: Decimal = Field(gt=0, max_digits=20, decimal_places=8)

    @field_validator("currency", mode="before")
    @classmethod
    def _upper(cls, v):
        return v.upper() if isinstance(v, str) else v


class FxRatesUpsertCmd(BaseModel):
    items: list[FxMonthRateUpsertCmd] = Field(min_length=1, max_length=120)


class ExpenseCategoryDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    position: int


class ExpenseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    expense_date: date
    category_id: UUID
    category_name: str
    description: Optional[str] = None
    amount_pen: float
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ExpenseCreateCmd(BaseModel):
    expense_date: date
    category_id: UUID
    description: Optional[str] = Field(default=None, max_length=500)
    amount_pen: Decimal = Field(gt=0, max_digits=20, decimal_places=2)

    @field_validator("description")
    @classmethod
    def _strip(cls, v: Optional[str]) -> Optional[str]:
        cleaned = (v or "").strip()
        return cleaned or None


class ExpenseUpdateCmd(BaseModel):
    id: UUID
    expense_date: Optional[date] = None
    category_id: Optional[UUID] = None
    description: Optional[str] = Field(default=None, max_length=500)
    amount_pen: Optional[Decimal] = Field(default=None, gt=0, max_digits=20, decimal_places=2)

    @field_validator("description")
    @classmethod
    def _strip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return v.strip() or None


class ExpenseListDTO(BaseModel):
    items: list[ExpenseDTO]
    total_pen: float
