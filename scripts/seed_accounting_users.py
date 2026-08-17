#!/usr/bin/env python
"""
Script para crear los usuarios de contabilidad (rol `accounting`).

Ejecutar desde la raíz del proyecto (con venv/poetry activo):

    python -m scripts.seed_accounting_users

O con Poetry:
    poetry run python -m scripts.seed_accounting_users

Requisitos: .env configurado con la conexión a la base de datos.

Es idempotente: si el email ya existe, lo omite en vez de fallar.
"""
import asyncio
import sys
from pathlib import Path

# Añadir raíz del proyecto al path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Registrar modelos SQLAlchemy
import app.models_registry  # noqa: F401

from app.core.settings import get_settings
from app.core.security import SecurityUtils
from app.db.base import AsyncSessionLocal
from app.modules.auth.application.use_cases import CreateAuthService
from app.modules.users.application.schemas.user_schema import UserCreateCmd
from app.modules.users.application.use_cases import CreateUserUseCase
from app.modules.users.domain.enums import UserRole
from app.modules.users.infrastructure.unit_of_work import AsyncUserAuthUnitOfWork


# Usuarios a crear. Nombres/apellidos quedan vacíos: se completan luego
# desde el backoffice.
ACCOUNTING_USERS = [
    {"email": "rgarcia@brasper.com", "password": "Brasper2026!"},
    {"email": "dbasualdo@brasper.com", "password": "Brasper20026!"},
    {"email": "abravo@brasper.com", "password": "Brasper20026!"},
]


async def seed_accounting_users():
    """Crea los usuarios con rol accounting y sus credenciales de acceso."""
    print(f"Se crearán {len(ACCOUNTING_USERS)} usuarios con rol '{UserRole.accounting.value}'...")

    created = 0
    skipped = 0

    for data in ACCOUNTING_USERS:
        # Una sesión por usuario: si uno falla, no arrastra a los demás.
        async with AsyncSessionLocal() as session:
            uow = AsyncUserAuthUnitOfWork(session)
            auth_service = CreateAuthService(SecurityUtils(get_settings()), uow.auth_repository)
            use_case = CreateUserUseCase(uow, auth_service)

            cmd = UserCreateCmd(
                email=data["email"],
                password=data["password"],
                role=UserRole.accounting,
                is_agent=False,
            )
            try:
                result = await use_case.execute(cmd, profile_image=None)
                created += 1
                print(f"  ✓ {result.email} (rol: {result.role.value}) - id: {result.id}")
            except ValueError as e:
                skipped += 1
                print(f"  · {data['email']} omitido: {e}")
            except Exception as e:
                print(f"  ✗ Error en {data['email']}: {e}")
                raise

    print(f"\nListo. Creados: {created}. Omitidos: {skipped}.")


if __name__ == "__main__":
    asyncio.run(seed_accounting_users())
