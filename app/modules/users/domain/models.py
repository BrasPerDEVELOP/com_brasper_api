# app/modules/users/domain/models.py
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import String, Boolean, BigInteger, ForeignKey, Index, Integer, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.model_base import ORMBaseModel

if TYPE_CHECKING:
    from app.modules.transactions.domain.models import Transaction


class UserIdentification(ORMBaseModel):
    """Documento de identidad de un usuario.

    La unicidad de `(document_type, document_number)` vive en un índice único
    PARCIAL (`WHERE deleted = false`, migración 063), no en una constraint: el
    borrado es lógico y una constraint incondicional dejaba el documento
    bloqueado para siempre tras eliminar al usuario.
    """

    __tablename__ = "user_identifications"
    __table_args__ = (
        Index(
            "uq_user_identifications_type_number_alive",
            "document_type",
            "document_number",
            unique=True,
            postgresql_where=text("deleted = false"),
        ),
        {"schema": "user"},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_type: Mapped[str] = mapped_column(String(20), nullable=False)
    document_number: Mapped[str] = mapped_column(String(40), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    user: Mapped["User"] = relationship("User", back_populates="identifications")


class User(ORMBaseModel):
    __tablename__ = "user"
    __table_args__ = (
        Index(
            "uq_user_email_alive",
            "email",
            unique=True,
            postgresql_where=text("deleted = false AND email IS NOT NULL"),
        ),
        Index(
            "uq_user_document_number_alive",
            "document_number",
            unique=True,
            postgresql_where=text("deleted = false AND document_number IS NOT NULL"),
        ),
        {"schema": "user"},
    )

    auth_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    names: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    lastnames: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # Unicidad en índice parcial `uq_user_email_alive` (migración 063).
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    profile_image: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Unicidad en índice parcial `uq_user_document_number_alive` (migración 063).
    document_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    document_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # DocumentType enum value
    is_agent: Mapped[Optional[bool]] = mapped_column(Boolean, default=True, nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # UserRole enum value
    phone: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # hasta 15 dígitos
    code_phone: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # PhoneCode enum value (ej. +51)

    identifications: Mapped[list["UserIdentification"]] = relationship(
        "UserIdentification",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        order_by="UserIdentification.position",
    )

    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        foreign_keys="Transaction.user_id",
        back_populates="user",
        lazy="noload",
    )
