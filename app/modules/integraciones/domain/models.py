# app/modules/integraciones/domain/models.py
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.integraciones.domain.enums import IntegrationType, IntegrationTypeEnumType
from app.shared.model_base import ORMBaseModel


class Integration(ORMBaseModel):
    """Configuración de una integración con un proveedor externo (webhook, API, OAuth)."""
    __tablename__ = "integration"
    __table_args__ = {"schema": "integrations"}

    name: Mapped[str] = mapped_column(String(250), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    integration_type: Mapped[IntegrationType] = mapped_column(
        IntegrationTypeEnumType, nullable=False, index=True
    )
    config: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class SocialAccount(ORMBaseModel):
    """Vincula un usuario de la app con una cuenta de proveedor OAuth (Google, Facebook)."""
    __tablename__ = "social_account"
    __table_args__ = {"schema": "integrations"}

    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("user.user.id"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
