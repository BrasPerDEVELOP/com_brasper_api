# app/modules/coin/domain/models.py
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modules.coin.domain.enums import Currency, CurrencyEnumType
from app.shared.model_base import ORMBaseModel

if TYPE_CHECKING:
    from app.modules.transactions.domain.models import Transaction


class TaxRate(ORMBaseModel):
    """Tasa impositiva entre dos monedas (coin_a → coin_b) con valor tax."""
    __tablename__ = "tax_rate"
    __table_args__ = {"schema": "coin"}

    tax: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False, default=0)
    coin_a: Mapped[Currency] = mapped_column(CurrencyEnumType, nullable=False, index=True)
    coin_b: Mapped[Currency] = mapped_column(CurrencyEnumType, nullable=False, index=True)


class TaxRateTrial(ORMBaseModel):
    """Tasa prueba entre dos monedas (coin_a → coin_b) con valor tax. Misma estructura que TaxRate."""
    __tablename__ = "tax_rate_trial"
    __table_args__ = {"schema": "coin"}

    tax: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False, default=0)
    coin_a: Mapped[Currency] = mapped_column(CurrencyEnumType, nullable=False, index=True)
    coin_b: Mapped[Currency] = mapped_column(CurrencyEnumType, nullable=False, index=True)


class Commission(ORMBaseModel):
    """Comisión entre dos monedas (coin_a → coin_b): porcentaje, reversa y montos min/max."""
    __tablename__ = "commission"
    __table_args__ = {"schema": "coin"}

    coin_a: Mapped[Currency] = mapped_column(CurrencyEnumType, nullable=False, index=True)
    coin_b: Mapped[Currency] = mapped_column(CurrencyEnumType, nullable=False, index=True)
    percentage: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False, default=0)
    reverse: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False, default=0)
    min_amount: Mapped[Optional[float]] = mapped_column(Numeric(20, 8), nullable=True)
    max_amount: Mapped[Optional[float]] = mapped_column(Numeric(20, 8), nullable=True)


class CommissionAccounting(ORMBaseModel):
    """Comisión contable entre dos monedas (coin_a → coin_b): porcentaje, reversa y montos min/max."""
    __tablename__ = "commission_accounting"
    __table_args__ = {"schema": "coin"}

    coin_a: Mapped[Currency] = mapped_column(CurrencyEnumType, nullable=False, index=True)
    coin_b: Mapped[Currency] = mapped_column(CurrencyEnumType, nullable=False, index=True)
    percentage: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False, default=0)
    reverse: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False, default=0)
    min_amount: Mapped[Optional[float]] = mapped_column(Numeric(20, 8), nullable=True)
    max_amount: Mapped[Optional[float]] = mapped_column(Numeric(20, 8), nullable=True)

    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        foreign_keys="[Transaction.commission_accounting_id]",
        back_populates="commission_accounting",
        lazy="noload",
    )


class CommissionAccountingSettings(ORMBaseModel):
    """
    Settings globales de comisión contable bajo umbral.
    Una sola fila activa: si monto < amount_threshold → fixed_commission.
    """
    __tablename__ = "commission_accounting_settings"
    __table_args__ = {"schema": "coin"}

    amount_threshold: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False, default=100)
    fixed_commission: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False, default=3)


class CommissionTrial(ORMBaseModel):
    """Comisión de prueba entre dos monedas (coin_a → coin_b)."""
    __tablename__ = "commission_trial"
    __table_args__ = {"schema": "coin"}

    coin_a: Mapped[Currency] = mapped_column(CurrencyEnumType, nullable=False, index=True)
    coin_b: Mapped[Currency] = mapped_column(CurrencyEnumType, nullable=False, index=True)
    percentage: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False, default=0)
    reverse: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False, default=0)
    min_amount: Mapped[Optional[float]] = mapped_column(Numeric(20, 8), nullable=True)
    max_amount: Mapped[Optional[float]] = mapped_column(Numeric(20, 8), nullable=True)
