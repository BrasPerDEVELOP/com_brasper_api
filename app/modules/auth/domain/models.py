# app/modules/auth/domain/models.py
from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
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
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
