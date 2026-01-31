# app/core/containers/common.py
"""Dependencias comunes: settings, DB, security utils."""
import logging

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.core.security import SecurityUtils
from app.db.base import get_db

logger = logging.getLogger(__name__)

_settings = get_settings()
_security_utils = SecurityUtils(_settings)


def get_security_utils() -> SecurityUtils:
    """Singleton de SecurityUtils (contraseñas, tokens opacos)."""
    return _security_utils
