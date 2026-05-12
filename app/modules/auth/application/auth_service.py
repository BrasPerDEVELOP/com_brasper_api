# app/modules/auth/application/auth_service.py
"""Servicio de autenticación: cambio de contraseña, recuperación, etc. Usa Unit of Work."""
from typing import Optional
from uuid import UUID
import logging
from fastapi import Depends

from app.core.security import SecurityUtils
from app.core.unit_of_work import UnitOfWorkBase
from app.modules.auth.domain.credentials import Credentials
from app.modules.auth.infrastructure.dependencies import get_security_utils

logger = logging.getLogger(__name__)


class AuthService:
    """Operaciones de auth (cambio de contraseña, reset). Usa Unit of Work."""

    def __init__(
        self,
        uow: UnitOfWorkBase,
        security_utils: SecurityUtils = Depends(get_security_utils),
    ):
        self._uow = uow
        self.security_utils = security_utils

    async def change_password(
        self,
        user_id: UUID,
        current_password: str,
        new_password: str,
    ) -> bool:
        user = await self._uow.user_repository.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        credentials = await self._uow.auth_repository.get_by_id(user.auth_id)
        if not credentials:
            raise ValueError("Credentials not found")

        if not self.security_utils.verify_password(current_password, credentials.password):
            raise ValueError("Current password is incorrect")

        if not self.security_utils.is_password_strong(new_password):
            raise ValueError("New password does not meet security requirements")

        hashed_password = self.security_utils.hash_password(new_password)
        await self._uow.auth_repository.update_password(
            credentials.id,
            hashed_password,
            must_change_password=False,
        )
        await self._uow.commit()
        logger.info(f"Password changed for user: {user_id}")
        return True

    async def admin_reset_password(self, user_id: UUID, new_password: str) -> bool:
        user = await self._uow.user_repository.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        if not self.security_utils.is_password_strong(new_password):
            raise ValueError("New password does not meet security requirements")

        hashed_password = self.security_utils.hash_password(new_password)
        credentials = None
        if user.auth_id:
            credentials = await self._uow.auth_repository.get_by_id(user.auth_id)
        if not credentials:
            if not user.email:
                raise ValueError("User email is required to create credentials")
            credentials = await self._uow.auth_repository.create(
                Credentials(
                    username=user.email,
                    password=hashed_password,
                    recovery_code=None,
                    token=None,
                    must_change_password=True,
                )
            )
            user.auth_id = credentials.id
            await self._uow.user_repository.update(user)
            await self._uow.commit()
            logger.info(f"Credentials created with temporary password for user: {user_id}")
            return True

        await self._uow.auth_repository.update_password(
            credentials.id,
            hashed_password,
            must_change_password=True,
        )
        await self._uow.commit()
        logger.info(f"Temporary password assigned for user: {user_id}")
        return True

    async def generate_password_reset(self, email: str) -> Optional[str]:
        user = await self._uow.user_repository.get_by_email(email)
        if not user:
            logger.info(f"Password reset requested for non-existent email: {email}")
            return None

        recovery_code = self.security_utils.generate_recovery_code()
        await self._uow.auth_repository.update_recovery_code(user.auth_id, recovery_code)
        await self._uow.commit()
        logger.info(f"Password reset code generated for user: {user.id}")
        return recovery_code

    async def reset_password(
        self, username: str, recovery_code: str, new_password: str
    ) -> bool:
        credentials = await self._uow.auth_repository.get_by_username(username)
        if not credentials or not credentials.recovery_code:
            logger.warning(f"Password reset failed - Invalid username or no reset code: {username}")
            raise ValueError("Invalid username or recovery code")

        if not self.security_utils.secure_compare(recovery_code, credentials.recovery_code):
            logger.warning(f"Password reset failed - Invalid recovery code for: {username}")
            raise ValueError("Invalid recovery code")

        if not self.security_utils.is_password_strong(new_password):
            raise ValueError("New password does not meet security requirements")

        hashed_password = self.security_utils.hash_password(new_password)
        await self._uow.auth_repository.update_password(
            credentials.id,
            hashed_password,
            must_change_password=False,
        )
        await self._uow.auth_repository.update_recovery_code(credentials.id, None)
        await self._uow.commit()
        logger.info(f"Password reset successful for user: {username}")
        return True
