# app/modules/integraciones/domain/enums.py
"""Enums para el módulo de integraciones."""
import enum

from sqlalchemy import Enum as SaEnum


class IntegrationType(str, enum.Enum):
    """Tipo de integración con sistemas externos."""
    webhook = "webhook"
    api = "api"
    oauth = "oauth"


# Tipo ENUM de PostgreSQL en esquema integrations (creado por migraciones).
IntegrationTypeEnumType = SaEnum(
    IntegrationType, name="integration_type", schema="integrations", create_type=False
)
