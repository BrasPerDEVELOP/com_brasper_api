# app/modules/auth/domain/models.py
from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import Boolean, String, DateTime, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.model_base import ORMBaseModel


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
