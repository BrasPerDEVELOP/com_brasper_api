# app/modules/auth/application/use_cases/auth_use_cases.py
"""Casos de uso del módulo auth (login, verificación, creación de credenciales)."""
from uuid import uuid4
import logging
from fastapi import Depends

from app.core.security import SecurityUtils
from app.core.unit_of_work import UnitOfWorkBase
from app.modules.auth.application.schemas.auth_schema import (
    AuthCreateCmd,
    AuthReadDTO,
    TokenInfoDTO,
    UserInfoDTO,
)
from app.modules.auth.domain.credentials import Credentials
from app.modules.auth.infrastructure.dependencies import get_auth_repository, get_security_utils
from app.modules.auth.interfaces.auth_repository import AuthRepositoryInterface
from app.modules.users.interfaces.user_repository import UserRepositoryInterface

logger = logging.getLogger(__name__)


class LoginUseCase:
    """Login: valida credenciales, genera token, persiste con Unit of Work."""

    def __init__(
        self,
        uow: UnitOfWorkBase,
        security_utils: SecurityUtils = Depends(get_security_utils),
    ):
        self._uow = uow
        self.security_utils = security_utils

    async def execute(self, data: AuthCreateCmd, ip_address: str) -> TokenInfoDTO:
        logger.info(f"Login attempt from IP: {ip_address} for user: {data.username}")

        credentials = await self._uow.auth_repository.get_by_username(data.username)
        if not credentials:
            logger.warning(f"Login failed: user {data.username} not found")
            raise ValueError("Invalid username or password")

        is_valid = self.security_utils.verify_password(data.password, credentials.password)
        logger.debug(f"Password verification result for {data.username}: {is_valid}")

        if not is_valid:
            logger.warning(f"Login failed: incorrect password for user: {data.username}")
            raise ValueError("Invalid username or password")

        user = await self._uow.user_repository.get_by_auth_id(credentials.id)
        if not user:
            logger.error(f"User not found for auth_id: {credentials.id}")
            raise ValueError("User account not found")

        access_token = self.security_utils.generate_opaque_token(
            user_id=user.id,
            username=credentials.username,
        )
        await self._uow.auth_repository.update_token(credentials.id, access_token)
        await self._uow.commit()

        logger.info(f"Login successful for user: {credentials.username} - New session created")
        return TokenInfoDTO(
            token=access_token,
            user=UserInfoDTO.model_validate(user),
        )


class VerifyCredentialsUseCase:
    def __init__(
        self,
        auth_repo: AuthRepositoryInterface = Depends(get_auth_repository),
        security_utils: SecurityUtils = Depends(get_security_utils),
    ):
        self.auth_repo = auth_repo
        self.security_utils = security_utils

    async def execute(self, data: AuthCreateCmd) -> bool:
        credentials = await self.auth_repo.get_by_username(data.username)
        if not credentials:
            raise ValueError("Invalid username or password")
        if not self.security_utils.verify_password(data.password, credentials.password):
            raise ValueError("Invalid username or password")
        return True


class CreateAuthUseCase:
    """Caso de uso: crear credenciales de autenticación. No hace commit (lo hace el caller/UoW)."""

    def __init__(
        self,
        security_utils: SecurityUtils = Depends(get_security_utils),
        auth_repository: AuthRepositoryInterface = Depends(get_auth_repository),
    ):
        self.security_utils = security_utils
        self.auth_repository = auth_repository

    async def execute(self, cmd: AuthCreateCmd) -> AuthReadDTO:
        logger.info(f"Creating auth credentials for username: {cmd.username}")
        existing_auth = await self.auth_repository.get_by_username(cmd.username)
        if existing_auth:
            logger.warning(f"Auth creation failed - Username already exists: {cmd.username}")
            raise ValueError("Username already exists")

        if not self.security_utils.is_password_strong(cmd.password):
            raise ValueError("Password does not meet security requirements")

        hashed_password = self.security_utils.hash_password(cmd.password)
        credentials = Credentials(
            username=cmd.username,
            password=hashed_password,
            recovery_code=None,
            token=None,
        )

        created_credentials = await self.auth_repository.create(credentials)
        auth_id = getattr(created_credentials, "id", created_credentials)
        if auth_id is None:
            logger.warning("auth_id returned None, generating fallback UUID")
            auth_id = uuid4()

        logger.info(f"Auth credentials created successfully for username: {cmd.username}, ID: {auth_id}")
        return AuthReadDTO(id=auth_id)


# Alias para compatibilidad con container y user_service
CreateAuthService = CreateAuthUseCase
