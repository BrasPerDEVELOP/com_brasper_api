# app/modules/integraciones/interfaces/social_account_repository.py
from abc import abstractmethod
from typing import Optional

from app.shared.interface_base import BaseRepositoryInterface
from app.modules.integraciones.domain.models import SocialAccount


class SocialAccountRepositoryInterface(BaseRepositoryInterface[SocialAccount]):
    """Puerto de persistencia para SocialAccount."""

    @abstractmethod
    async def get_by_provider_and_provider_user_id(
        self, provider: str, provider_user_id: str
    ) -> Optional[SocialAccount]:
        """Obtiene la cuenta social por proveedor e id del usuario en el proveedor."""
        ...
