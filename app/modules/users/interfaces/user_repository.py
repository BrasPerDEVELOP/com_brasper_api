from abc import abstractmethod
from typing import List, Optional, Sequence
from uuid import UUID
from app.shared.interface_base import BaseRepositoryInterface
from app.modules.users.domain.models import User


class UserRepositoryInterface(BaseRepositoryInterface[User]):
    """Puerto de persistencia para la entidad *User*."""

    @abstractmethod
    async def list_filtered(self, user_id: Optional[UUID] = None, role: Optional[str] = None,
                            country: Optional[str] = None, search: Optional[str] = None) -> List[User]:
        ...

    @abstractmethod
    async def list_countries(self, role: Optional[str] = None) -> List[str]:
        ...

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        ...

    @abstractmethod
    async def soft_delete_identifications(self, user_id: UUID) -> None:
        """Acompaña al borrado lógico del usuario.

        El índice único de `(document_type, document_number)` solo mira filas
        vivas; si estas no se marcan, el documento del usuario eliminado queda
        bloqueado y no se puede volver a registrar a esa persona.
        """
        ...

    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[User]:
        ...

    @abstractmethod
    async def get_by_auth_id(self, auth_id: UUID) -> Optional[User]:
        ...

    @abstractmethod
    async def list_ids_by_roles(self, roles: Sequence[str]) -> List[UUID]:
        """IDs de usuarios activos y no borrados cuyo `role` está en `roles`."""
        ...
