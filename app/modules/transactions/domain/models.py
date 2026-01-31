# app/modules/transactions/domain/models.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Numeric, Enum, String, ForeignKey, DateTime, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modules.coin.domain.enums import Currency
from app.modules.transactions.domain.enums import (
    TransactionStatus,
    BankCountry,
    AccountFlowType,
    AccountHolderType,
)
from app.shared.model_base import ORMBaseModel


class Transaction(ORMBaseModel):
    """Transacción: bank_account, user, tax_rate, commission, montos, code, fechas, vouchers."""
    __tablename__ = "transactions"
    __table_args__ = {"schema": "transaction"}

    # FKs
    bank_account_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("transaction.bank_accounts.id"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("user.user.id"),
        nullable=False,
        index=True,
    )
    tax_rate_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("coin.tax_rate.id"),
        nullable=False,
        index=True,
    )
    commission_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("coin.commission.id"),
        nullable=False,
        index=True,
    )

    status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus),
        nullable=False,
        default=TransactionStatus.pending,
        index=True,
    )

    # Montos y código
    origin_amount: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    destination_amount: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)

    # Fechas
    send_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Vouchers (imagen: path o URL)
    send_voucher: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    payment_voucher: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relaciones
    bank_account: Mapped["BankAccount"] = relationship(
        "BankAccount", back_populates="transactions", lazy="noload"
    )


class Bank(ORMBaseModel):
    """Cuenta bancaria o Pix por moneda/país: banco, cuenta/pix, empresa, moneda, imagen."""
    __tablename__ = "banks"
    __table_args__ = {"schema": "transaction"}

    bank: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    account: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    pix: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    company: Mapped[str] = mapped_column(String(200), nullable=False)
    currency: Mapped[Currency] = mapped_column(Enum(Currency), nullable=False, index=True)
    image: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[BankCountry] = mapped_column(
        Enum(BankCountry, schema="transaction", name="bank_country"), nullable=False, index=True
    )

    bank_accounts: Mapped[list["BankAccount"]] = relationship(
        "BankAccount", back_populates="bank", lazy="noload"
    )


class BankAccount(ORMBaseModel):
    """Cuenta bancaria de un usuario: titular, banco, tipo (origen/destino), personal/jurídica, datos Perú/Brasil."""
    __tablename__ = "bank_accounts"
    __table_args__ = {"schema": "transaction"}

    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("user.user.id"),
        nullable=False,
        index=True,
    )
    bank_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("transaction.banks.id"),
        nullable=False,
        index=True,
    )
    account_flow: Mapped[AccountFlowType] = mapped_column(
        Enum(AccountFlowType, schema="transaction", name="account_flow_type"),
        nullable=False,
        index=True,
    )
    account_holder_type: Mapped[AccountHolderType] = mapped_column(
        Enum(AccountHolderType, schema="transaction", name="account_holder_type"),
        nullable=False,
        index=True,
    )
    bank_country: Mapped[BankCountry] = mapped_column(
        Enum(BankCountry, schema="transaction", name="bank_country"),
        nullable=False,
        index=True,
    )

    # Titular (Perú)
    holder_names: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    holder_surnames: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    document_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Empresarial (opcional)
    business_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ruc_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    legal_representative_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    legal_representative_document: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Cuenta Perú
    account_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    account_number_confirmation: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cci_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cci_number_confirmation: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Brasil / PIX
    pix_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    pix_key_confirmation: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    pix_key_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    cpf: Mapped[Optional[str]] = mapped_column(String(14), nullable=True)

    # Relaciones
    bank: Mapped["Bank"] = relationship("Bank", back_populates="bank_accounts", lazy="noload")
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="bank_account", lazy="noload"
    )


class Coupon(ORMBaseModel):
    """Cupón: código, descuento %, máximo usos, moneda origen/destino, fechas inicio/fin, activo."""
    __tablename__ = "coupons"
    __table_args__ = {"schema": "transaction"}

    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    discount_percentage: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    max_uses: Mapped[int] = mapped_column(Integer, nullable=False)
    origin_currency: Mapped[Currency] = mapped_column(Enum(Currency), nullable=False, index=True)
    destination_currency: Mapped[Currency] = mapped_column(Enum(Currency), nullable=False, index=True)
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)


