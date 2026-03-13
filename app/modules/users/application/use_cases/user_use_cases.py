# app/modules/users/application/use_cases/user_use_cases.py
"""Casos de uso del módulo users."""
from uuid import UUID
from typing import Optional, List
import logging

from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError

from app.core.unit_of_work import UnitOfWorkBase
from app.shared.services.file_service import save_profile_image
from app.modules.auth.application.use_cases import CreateAuthService
from app.modules.auth.application.schemas.auth_schema import UserInfoDTO
from app.modules.users.domain.models import User
from app.modules.users.interfaces.user_repository import UserRepositoryInterface
from app.modules.users.application.schemas.user_schema import (
    UserCreateCmd,
    UserNameDTO,
    UserReadGeneralDTO,
    UserUpdateCmd,
    UserReadDTO,
)

logger = logging.getLogger(__name__)


class GetUserByIdUseCase:
    def __init__(self, repo: UserRepositoryInterface):
        self.repo = repo

    async def execute(self, user_id: UUID) -> Optional[UserReadDTO]:
        logger.info(f"Obteniendo usuario con ID: {user_id}")
        user = await self.repo.get(user_id)
        if not user:
            return None
        return UserReadDTO.model_validate(user)


class GetUserByEmailUseCase:
    def __init__(self, repo: UserRepositoryInterface):
        self.repo = repo

    async def execute(self, email: str) -> Optional[UserReadGeneralDTO]:
        logger.info(f"Buscando usuario con email: {email}")
        user = await self.repo.get_by_email(email)
        if not user:
            return None
        return UserReadGeneralDTO.model_validate(user)


class GetUserByAuthIdUseCase:
    def __init__(self, repo: UserRepositoryInterface):
        self.repo = repo

    async def execute(self, auth_id: UUID) -> Optional[UserReadDTO]:
        logger.info(f"Buscando usuario con auth_id: {auth_id}")
        user = await self.repo.get_by_auth_id(auth_id)
        if not user:
            return None
        return UserReadDTO.model_validate(user)


class CreateUserUseCase:
    """Crea usuario (y credenciales auth si hay email/password). Usa Unit of Work."""

    def __init__(
        self,
        uow: UnitOfWorkBase,
        auth_service: CreateAuthService,
    ):
        self._uow = uow
        self._auth_service = auth_service

    async def execute(self, cmd: UserCreateCmd, profile_image: Optional[UploadFile]) -> UserReadDTO:
        logger.info("Creando nuevo usuario")
        try:
            auth_id = None
            if cmd.email:
                existing_user = await self._uow.user_repository.get_by_email(cmd.email)
                if existing_user:
                    raise ValueError("Ya existe un usuario con este email")
                auth_cmd = cmd.to_auth_cmd()
                if auth_cmd and auth_cmd.password:
                    auth_result = await self._auth_service.execute(auth_cmd)
                    auth_id = auth_result.id

            image_path: Optional[str] = None
            if profile_image:
                image_path = await save_profile_image(profile_image)

            user = User(
                auth_id=auth_id,
                names=cmd.names,
                lastnames=cmd.lastnames,
                email=cmd.email,
                profile_image=image_path or cmd.profile_image,
                document_number=cmd.document_number,
                document_type=cmd.document_type.value if cmd.document_type else None,
                is_agent=cmd.is_agent,
                role=cmd.role.value if cmd.role else None,
                phone=cmd.phone,
                code_phone=cmd.code_phone.value if cmd.code_phone else None,
            )

            saved = await self._uow.user_repository.add(user)
            await self._uow.commit()
            saved = await self._uow.user_repository.get(saved.id)
            logger.info(f"Usuario creado: {saved.id}")
            return UserReadDTO.model_validate(saved)
        except IntegrityError as e:
            await self._uow.rollback()
            err_msg = str(getattr(e, "orig", e))
            if "document_number" in err_msg:
                raise ValueError("Ya existe un usuario con este número de documento")
            if "email" in err_msg:
                raise ValueError("Ya existe un usuario con este email")
            raise ValueError("Los datos ingresados ya existen para otro usuario") from e
        except Exception as e:
            await self._uow.rollback()
            raise e


class UpdateUserUseCase:
    """Actualiza usuario. Usa Unit of Work."""

    def __init__(self, uow: UnitOfWorkBase):
        self._uow = uow

    async def execute(self, cmd: UserUpdateCmd) -> Optional[UserReadDTO]:
        try:
            existing_user = await self._uow.user_repository.get(cmd.id)
            if not existing_user:
                return None

            # Actualización explícita por campo (evita problemas con model_dump y enums)
            if "names" in cmd.model_fields_set:
                existing_user.names = cmd.names
            if "lastnames" in cmd.model_fields_set:
                existing_user.lastnames = cmd.lastnames
            if "email" in cmd.model_fields_set:
                existing_user.email = cmd.email
            if "profile_image" in cmd.model_fields_set:
                existing_user.profile_image = cmd.profile_image
            if "document_number" in cmd.model_fields_set:
                existing_user.document_number = cmd.document_number
            if "document_type" in cmd.model_fields_set:
                existing_user.document_type = cmd.document_type.value if cmd.document_type else None
            if "is_agent" in cmd.model_fields_set:
                existing_user.is_agent = cmd.is_agent
            if "role" in cmd.model_fields_set:
                existing_user.role = cmd.role.value if cmd.role else None
            if "phone" in cmd.model_fields_set:
                existing_user.phone = cmd.phone
            if "code_phone" in cmd.model_fields_set:
                existing_user.code_phone = cmd.code_phone.value if cmd.code_phone else None

            updated_user = await self._uow.user_repository.update(existing_user)
            await self._uow.commit()
            updated_user = await self._uow.user_repository.get(updated_user.id)
            logger.info(f"Usuario actualizado: {updated_user.id}")
            return UserReadDTO.model_validate(updated_user) if updated_user else None
        except Exception as e:
            await self._uow.rollback()
            raise e


class DeleteUserUseCase:
    """Elimina usuario y sus credenciales auth. Usa Unit of Work."""

    def __init__(self, uow: UnitOfWorkBase):
        self._uow = uow

    async def execute(self, user_id: UUID):
        try:
            user = await self._uow.user_repository.get(user_id)
            auth_id = user.auth_id if user else None

            await self._uow.user_repository.delete(user_id)
            if auth_id:
                await self._uow.auth_repository.delete(auth_id)
                logger.info(f"Credenciales eliminadas: {auth_id}")

            await self._uow.commit()
            logger.info(f"Usuario eliminado: {user_id}")
        except Exception as e:
            await self._uow.rollback()
            raise e


def _build_user_query_filter(
    user_id: Optional[UUID] = None,
    role: Optional[str] = None,
):
    """Construye QueryFilter para user_id y/o role."""
    from app.shared.query_filter import FilterSchema, OperatorEnum, QueryFilter

    filters = []
    if user_id is not None:
        filters.append(FilterSchema(field="id", value=user_id, operator=OperatorEnum.EQ))
    if role is not None and str(role).strip():
        filters.append(FilterSchema(field="role", value=role, operator=OperatorEnum.EQ))
    return QueryFilter(filters=filters) if filters else None


class ListUsersWithDetailsUseCase:
    def __init__(self, repo: UserRepositoryInterface):
        self.repo = repo

    async def execute(
        self,
        user_id: Optional[UUID] = None,
        role: Optional[str] = None,
    ) -> List[UserInfoDTO]:
        try:
            query_filter = _build_user_query_filter(user_id=user_id, role=role)
            users = await self.repo.list(query_filter=query_filter)
            return [UserInfoDTO.model_validate(user) for user in users]
        except Exception as e:
            await self.repo.rollback()
            raise e


class ListUserUseCase:
    def __init__(self, repo: UserRepositoryInterface):
        self.repo = repo

    async def execute(
        self,
        user_id: Optional[UUID] = None,
        role: Optional[str] = None,
    ) -> List[UserReadGeneralDTO]:
        try:
            query_filter = _build_user_query_filter(user_id=user_id, role=role)
            users = await self.repo.list(query_filter=query_filter)
            return [UserReadGeneralDTO.model_validate(user) for user in users]
        except Exception as e:
            await self.repo.rollback()
            raise e


class ListSalesUserIdsUseCase:
    """Devuelve los IDs de usuarios con rol sales."""

    def __init__(self, repo: UserRepositoryInterface):
        self.repo = repo

    async def execute(self) -> List[UUID]:
        try:
            query_filter = _build_user_query_filter(role="sales")
            users = await self.repo.list(query_filter=query_filter)
            return [user.id for user in users]
        except Exception as e:
            await self.repo.rollback()
            raise e


class ListUserNameUseCase:
    def __init__(self, repo: UserRepositoryInterface):
        self.repo = repo

    async def execute(
        self,
        user_id: Optional[UUID] = None,
        role: Optional[str] = None,
    ) -> List[UserNameDTO]:
        try:
            from app.shared.query_filter import FilterSchema, OperatorEnum, QueryFilter

            filters = [
                FilterSchema(field="enable", value=True, operator=OperatorEnum.EQ),
                FilterSchema(field="is_agent", value=True, operator=OperatorEnum.EQ),
            ]
            if user_id is not None:
                filters.append(FilterSchema(field="id", value=user_id, operator=OperatorEnum.EQ))
            if role is not None and str(role).strip():
                filters.append(FilterSchema(field="role", value=role, operator=OperatorEnum.EQ))
            query_filter = QueryFilter(filters=filters)
            users = await self.repo.list(query_filter=query_filter)
            return [
                UserNameDTO.model_validate({
                    "id": user.id,
                    "names": user.names,
                    "lastnames": user.lastnames,
                })
                for user in users
            ]
        except Exception as e:
            await self.repo.rollback()
            raise e
