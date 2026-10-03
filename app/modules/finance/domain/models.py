# app/modules/finance/domain/models.py
"""Tablas del esquema ``finance``.

- ``fx_month_rates``: tasa de conversión a soles por (año, mes, moneda). La carga
  gerencia a mano y es la que usa el panel gerencial para expresar en soles los
  montos en reales y dólares (igual que su Excel).
- ``expense_categories``: catálogo cerrado de categorías de gasto (Planilla,
  Viáticos, Legal, …).
- ``expenses``: egresos de la empresa, siempre en soles.
"""
from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modules.coin.domain.enums import Currency, CurrencyEnumType
from app.shared.model_base import ORMBaseModel


class FxMonthRate(ORMBaseModel):
    __tablename__ = "fx_month_rates"
    __table_args__ = (
        UniqueConstraint("year", "month", "currency", name="uq_fx_month_rate"),
        {"schema": "finance"},
    )

    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[Currency] = mapped_column(CurrencyEnumType, nullable=False)
    # Cuántos soles vale 1 unidad de ``currency`` ese mes.
    rate_to_pen: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)


class ExpenseCategory(ORMBaseModel):
    __tablename__ = "expense_categories"
    __table_args__ = {"schema": "finance"}

    name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    expenses: Mapped[list["Expense"]] = relationship(
        "Expense", back_populates="category", lazy="noload"
    )


class Expense(ORMBaseModel):
    __tablename__ = "expenses"
    __table_args__ = {"schema": "finance"}

    expense_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    category_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("finance.expense_categories.id"),
        nullable=False,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Siempre en soles (decisión del primer incremento del panel gerencial).
    amount_pen: Mapped[float] = mapped_column(Numeric(20, 2), nullable=False)

    category: Mapped["ExpenseCategory"] = relationship(
        "ExpenseCategory", back_populates="expenses", lazy="joined"
    )
