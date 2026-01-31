# app/modules/auth/domain
from app.modules.auth.domain.models import AuthModel
from app.modules.auth.domain.credentials import Credentials

__all__ = [
    "AuthModel",
    "Credentials",
]
