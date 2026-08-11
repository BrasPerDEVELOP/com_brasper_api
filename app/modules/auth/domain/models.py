# app/modules/auth/domain/models.py
from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.model_base import ORMBase, ORMBaseModel


class AuthModel(ORMBaseModel):
    __tablename__ = "auth_login"
    __table_args__ = {"schema": "user"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    recovery_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    token: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

class RolePermissionModel(ORMBaseModel):
    __tablename__ = "role_permission"
    __table_args__ = (
        UniqueConstraint("role", name="uq_role_permission_role"),
        {"schema": "user"},
    )

    role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    permissions: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)


class AuthSessionModel(ORMBase):
    __tablename__ = "auth_session"
    __table_args__ = (
        CheckConstraint(
            "client_app IN ('backoffice', 'www')",
            name="ck_auth_session_client_app",
        ),
        Index("ix_user_auth_session_user_id", "user_id"),
        Index("ix_user_auth_session_family_id", "family_id"),
        Index(
            "ix_user_auth_session_refresh_token_hash",
            "refresh_token_hash",
            unique=True,
        ),
        {"schema": "user"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.user.id", ondelete="CASCADE"), nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, default=uuid.uuid4)
    parent_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("user.auth_session.id", ondelete="SET NULL"), nullable=True)
    rotation_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    client_app: Mapped[str] = mapped_column(String(50), nullable=False, default="backoffice")
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoke_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reuse_detected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
