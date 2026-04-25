from app.shared.interface_base import BaseRepositoryInterface
from app.modules.brasper.domain.models import ContacForm


class ContactFormRepositoryInterface(BaseRepositoryInterface[ContacForm]):
    """Puerto de persistencia para envíos del formulario de contacto."""

    ...
