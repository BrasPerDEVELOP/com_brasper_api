# app/modules/users/domain/models.py
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import String, Boolean, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.model_base import ORMBaseModel

if TYPE_CHECKING:
    from app.modules.transactions.domain.models import Transaction


class User(ORMBaseModel):
    __tablename__ = "user"
    __table_args__ = {"schema": "user"}

    auth_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    names: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    lastnames: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    profile_image: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    document_number: Mapped[Optional[str]] = mapped_column(String(20), unique=True, nullable=True)
    document_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # DocumentType enum value
    is_agent: Mapped[Optional[bool]] = mapped_column(Boolean, default=True, nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # UserRole enum value
    phone: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # hasta 15 dígitos
    code_phone: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # PhoneCode enum value (ej. +51)

    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        foreign_keys="Transaction.user_id",
        back_populates="user",
        lazy="noload",
    )
