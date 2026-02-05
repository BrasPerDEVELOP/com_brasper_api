# app/modules/integraciones/interfaces/integration_repository.py
from abc import abstractmethod
from typing import Optional

from app.shared.interface_base import BaseRepositoryInterface
from app.modules.integraciones.domain.models import Integration


class IntegrationRepositoryInterface(BaseRepositoryInterface[Integration]):
    """Puerto de persistencia para Integration."""

    @abstractmethod
    async def get_by_provider(self, provider: str) -> Optional[Integration]:
        """Obtiene la integración activa para un proveedor (ej. google, facebook)."""
        ...
