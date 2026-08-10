# app/modules/transactions/domain/models.py
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

if TYPE_CHECKING:
    from app.modules.users.domain.models import User

from sqlalchemy import Numeric, Enum, String, ForeignKey, DateTime, Boolean, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modules.coin.domain.enums import Currency, CurrencyEnumType
from app.modules.transactions.domain.enums import (
    TransactionStatus,
    BankCountry,
    AccountFlowType,
    SocialActor,
)
from app.shared.model_base import ORMBaseModel


class Transaction(ORMBaseModel):
    """Transacción con bancos independientes para destino y razón social.

    ``bank_id``/``bank_name`` identifican el banco de la cuenta destino, mientras
    ``social_reason_bank_id``/``company_name`` conservan la razón social elegida.
    """
    __tablename__ = "transactions"
    __table_args__ = {"schema": "transaction"}

    # FKs
    bank_account_origin_id: Mapped[Optional[UUID]] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("transaction.bank_accounts.id"),
        nullable=True,
        index=True,
    )
    bank_account_destination_id: Mapped[UUID] = mapped_column(
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
    agent_id: Mapped[Optional[UUID]] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("user.user.id"),
        nullable=True,
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
    bank_id: Mapped[Optional[UUID]] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("transaction.banks.id"),
        nullable=True,
        index=True,
    )
    social_reason_bank_id: Mapped[Optional[UUID]] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("transaction.banks.id"),
        nullable=True,
        index=True,
    )
    bank_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus, schema="transaction", name="transaction_status"),
        nullable=False,
        default=TransactionStatus.verification,
        index=True,
    )
    # Montos y código
    origin_amount: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    destination_amount: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    operation_number: Mapped[Optional[str]] = mapped_column(
        String(120), nullable=True, index=True
    )
    # datos calculadora
    commission_result: Mapped[Optional[float]] = mapped_column(Numeric(20, 8), nullable=True)
    total_to_send: Mapped[Optional[float]] = mapped_column(Numeric(20, 8), nullable=True)
    tax_amount: Mapped[Optional[float]] = mapped_column(Numeric(20, 8), nullable=True)
    coupon_id: Mapped[Optional[UUID]] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("transaction.coupons.id"),
        nullable=True,
        index=True,
    )
    # datos calculadora cupon
    coupon_discount_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    coupon_origin_amount: Mapped[Optional[float]] = mapped_column(Numeric(20, 8), nullable=True)
    coupon_destination_amount: Mapped[Optional[float]] = mapped_column(Numeric(20, 8), nullable=True)
    coupon_discount_percentage: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    coupon_discount_commission: Mapped[Optional[float]] = mapped_column(Numeric(20, 8), nullable=True)
    coupon_discount_total_to_send: Mapped[Optional[float]] = mapped_column(Numeric(20, 8), nullable=True)

    # Fechas
    send_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Vouchers (imagen: path o URL)
    send_voucher: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    payment_voucher: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    checked_image: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    send_vouchers: Mapped[Optional[list[str]]] = mapped_column(JSONB, nullable=True)
    payment_vouchers: Mapped[Optional[list[str]]] = mapped_column(JSONB, nullable=True)
    checked_images: Mapped[Optional[list[str]]] = mapped_column(JSONB, nullable=True)

    # Checklist
    checked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)

    # Relaciones
    bank_account_origin: Mapped[Optional["BankAccount"]] = relationship(
        "BankAccount",
        foreign_keys=[bank_account_origin_id],
        back_populates="transactions_as_origin",
        lazy="noload",
    )
    bank_account_destination: Mapped["BankAccount"] = relationship(
        "BankAccount",
        foreign_keys=[bank_account_destination_id],
        back_populates="transactions_as_destination",
        lazy="noload",
    )
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="transactions",
        lazy="noload",
    )
    coupon: Mapped["Coupon"] = relationship(
        "Coupon",
        foreign_keys=[coupon_id],
        back_populates="transactions",
        lazy="noload",
    )
    bank: Mapped[Optional["Bank"]] = relationship(
        "Bank",
        foreign_keys=[bank_id],
        back_populates="transactions",
        lazy="noload",
    )
    social_reason_bank: Mapped[Optional["Bank"]] = relationship(
        "Bank",
        foreign_keys=[social_reason_bank_id],
        back_populates="social_reason_transactions",
        lazy="noload",
    )
    destinations: Mapped[list["TransactionDestination"]] = relationship(
        "TransactionDestination",
        back_populates="transaction",
        cascade="all, delete-orphan",
        order_by="TransactionDestination.position",
        lazy="noload",
    )
    tags: Mapped[list["Tag"]] = relationship(
        "Tag",
        secondary="transaction.transaction_tags",
        back_populates="transactions",
        order_by="Tag.position, Tag.label",
        lazy="noload",
    )


class TransactionDestination(ORMBaseModel):
    """Parte del monto destino enviada a una cuenta bancaria del cliente."""

    __tablename__ = "transaction_destinations"
    __table_args__ = (
        UniqueConstraint(
            "transaction_id",
            "bank_account_id",
            name="uq_transaction_destinations_transaction_account",
        ),
        {"schema": "transaction"},
    )

    transaction_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("transaction.transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bank_account_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("transaction.bank_accounts.id"),
        nullable=False,
        index=True,
    )
    amount: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    transaction: Mapped["Transaction"] = relationship(
        "Transaction", back_populates="destinations", lazy="noload"
    )
    bank_account: Mapped["BankAccount"] = relationship(
        "BankAccount", back_populates="transaction_destinations", lazy="noload"
    )


class Bank(ORMBaseModel):
    """Cuenta bancaria o Pix por moneda/país: banco, cuenta/pix, empresa, moneda, imagen."""
    __tablename__ = "banks"
    __table_args__ = {"schema": "transaction"}

    bank: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    account: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    pix: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    company: Mapped[str] = mapped_column(String(200), nullable=False)
    currency: Mapped[Currency] = mapped_column(CurrencyEnumType, nullable=False, index=True)
    image: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    country: Mapped[BankCountry] = mapped_column(
        Enum(BankCountry, schema="transaction", name="bank_country"), nullable=False, index=True
    )
    social_actor: Mapped[Optional[SocialActor]] = mapped_column(
        Enum(SocialActor, schema="transaction", name="account_holder_type"),
        nullable=True,
        index=True,
    )

    bank_accounts: Mapped[list["BankAccount"]] = relationship(
        "BankAccount", back_populates="bank", lazy="noload"
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        foreign_keys="[Transaction.bank_id]",
        back_populates="bank",
        lazy="noload",
    )
    social_reason_transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        foreign_keys="[Transaction.social_reason_bank_id]",
        back_populates="social_reason_bank",
        lazy="noload",
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
    account_holder_type: Mapped[SocialActor] = mapped_column(
        Enum(SocialActor, schema="transaction", name="account_holder_type"),
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
    document_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Empresarial (opcional)
    business_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ruc_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    legal_representative_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    legal_representative_document: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Cuenta Perú
    account_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cci_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Brasil / PIX
    pix_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    pix_key_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    cpf: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relaciones
    bank: Mapped["Bank"] = relationship("Bank", back_populates="bank_accounts", lazy="noload")
    transactions_as_origin: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        foreign_keys="[Transaction.bank_account_origin_id]",
        back_populates="bank_account_origin",
        lazy="noload",
    )
    transactions_as_destination: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        foreign_keys="[Transaction.bank_account_destination_id]",
        back_populates="bank_account_destination",
        lazy="noload",
    )
    transaction_destinations: Mapped[list["TransactionDestination"]] = relationship(
        "TransactionDestination",
        back_populates="bank_account",
        lazy="noload",
    )


class Coupon(ORMBaseModel):
    """Cupón: código, descuento %, máximo usos, moneda origen/destino, fechas inicio/fin, activo."""
    __tablename__ = "coupons"
    __table_args__ = {"schema": "transaction"}

    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    discount_percentage: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    max_uses: Mapped[int] = mapped_column(Integer, nullable=False)
    origin_currency: Mapped[Optional[Currency]] = mapped_column(CurrencyEnumType, nullable=True, index=True)
    destination_currency: Mapped[Optional[Currency]] = mapped_column(CurrencyEnumType, nullable=True, index=True)
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    coupon_type: Mapped[str] = mapped_column(String(20), nullable=False, default="STANDARD", index=True)
    lifecycle_status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE", index=True)
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    per_user_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    exchange_rate_scopes: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        back_populates="coupon",
        lazy="noload",
    )


class CouponRedemption(ORMBaseModel):
    """Canje de cupón por usuario/transacción (límites per_user y reversas).

    La tabla física conserva el schema `world_cup` (migración 050) para no
    requerir migración de datos; el módulo world_cup fue retirado el 2026-07-22.
    """
    __tablename__ = "coupon_redemptions"
    __table_args__ = {"schema": "world_cup"}

    coupon_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("transaction.coupons.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("user.user.id", ondelete="CASCADE"), nullable=False)
    transaction_id: Mapped[Optional[UUID]] = mapped_column(PgUUID(as_uuid=True), ForeignKey("transaction.transactions.id", ondelete="SET NULL"), nullable=True)


class Tag(ORMBaseModel):
    """Etiqueta que ventas aplica a una transacción (ej. «Cliente nuevo»).

    ``counts_as_new_client`` marca la única etiqueta que alimenta el indicador de
    clientes nuevos del día; la unicidad se garantiza en el caso de uso, no con
    una constraint, porque el borrado es lógico (``deleted``) y un índice único
    parcial complicaría la reactivación de etiquetas.

    ``active`` es distinto de ``deleted``: una etiqueta inactiva deja de ofrecerse
    al registrar, pero sigue visible en las transacciones que ya la tenían.
    """

    __tablename__ = "tags"
    __table_args__ = {"schema": "transaction"}

    label: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    color: Mapped[str] = mapped_column(String(20), nullable=False, default="slate")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    counts_as_new_client: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        secondary="transaction.transaction_tags",
        back_populates="tags",
        lazy="noload",
    )


class TransactionTag(ORMBaseModel):
    """Puente transacción ↔ etiqueta.

    Se borra en cascada con la transacción y con la etiqueta: si se elimina una
    etiqueta del catálogo, desaparece de las transacciones que la tenían.
    """

    __tablename__ = "transaction_tags"
    __table_args__ = (
        UniqueConstraint("transaction_id", "tag_id", name="uq_transaction_tag"),
        {"schema": "transaction"},
    )

    transaction_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("transaction.transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tag_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("transaction.tags.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
