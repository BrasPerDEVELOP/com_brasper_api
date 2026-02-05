# app/modules/integraciones/application/schemas/integration_schema.py
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.integraciones.domain.enums import IntegrationType


class IntegrationCreateCmd(BaseModel):
    name: str
    provider: str
    integration_type: IntegrationType
    config: Optional[Dict[str, Any]] = None
    description: Optional[str] = None


class IntegrationUpdateCmd(BaseModel):
    id: UUID
    name: Optional[str] = None
    provider: Optional[str] = None
    integration_type: Optional[IntegrationType] = None
    config: Optional[Dict[str, Any]] = None
    description: Optional[str] = None


class IntegrationReadDTO(BaseModel):
    id: UUID
    name: str
    provider: str
    integration_type: IntegrationType
    config: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    created_at: datetime
    created_by: Optional[str] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
