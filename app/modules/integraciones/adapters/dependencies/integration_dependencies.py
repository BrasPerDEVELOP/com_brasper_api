# app/modules/integraciones/adapters/dependencies/integration_dependencies.py
"""Inyección de dependencias del módulo integraciones para las rutas (adapters)."""
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.core.containers.common import get_security_utils
from app.core.containers.unit_of_work import get_unit_of_work
from app.modules.users.infrastructure.unit_of_work import AsyncUserAuthUnitOfWork
from app.modules.integraciones.interfaces.integration_repository import IntegrationRepositoryInterface
from app.modules.integraciones.interfaces.social_account_repository import (
    SocialAccountRepositoryInterface,
)
from app.modules.integraciones.infrastructure.repository import (
    SQLAlchemyIntegrationRepository,
    SQLAlchemySocialAccountRepository,
)
from app.modules.integraciones.application.use_cases import (
    GetIntegrationByIdUseCase,
    ListIntegrationsUseCase,
    CreateIntegrationUseCase,
    UpdateIntegrationUseCase,
    DeleteIntegrationUseCase,
    GetOAuthAuthorizeUrlUseCase,
    OAuthCallbackUseCase,
)


def get_integration_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> IntegrationRepositoryInterface:
    return SQLAlchemyIntegrationRepository(db)


def get_social_account_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SocialAccountRepositoryInterface:
    return SQLAlchemySocialAccountRepository(db)


def get_integration_by_id_uc(
    repo: Annotated[IntegrationRepositoryInterface, Depends(get_integration_repository)],
) -> GetIntegrationByIdUseCase:
    return GetIntegrationByIdUseCase(repo)


def list_integrations_uc(
    repo: Annotated[IntegrationRepositoryInterface, Depends(get_integration_repository)],
) -> ListIntegrationsUseCase:
    return ListIntegrationsUseCase(repo)


def create_integration_uc(
    repo: Annotated[IntegrationRepositoryInterface, Depends(get_integration_repository)],
) -> CreateIntegrationUseCase:
    return CreateIntegrationUseCase(repo)


def update_integration_uc(
    repo: Annotated[IntegrationRepositoryInterface, Depends(get_integration_repository)],
) -> UpdateIntegrationUseCase:
    return UpdateIntegrationUseCase(repo)


def delete_integration_uc(
    repo: Annotated[IntegrationRepositoryInterface, Depends(get_integration_repository)],
) -> DeleteIntegrationUseCase:
    return DeleteIntegrationUseCase(repo)


GetIntegrationByIdUseCaseDep = Annotated[GetIntegrationByIdUseCase, Depends(get_integration_by_id_uc)]
ListIntegrationsUseCaseDep = Annotated[ListIntegrationsUseCase, Depends(list_integrations_uc)]
CreateIntegrationUseCaseDep = Annotated[CreateIntegrationUseCase, Depends(create_integration_uc)]
UpdateIntegrationUseCaseDep = Annotated[UpdateIntegrationUseCase, Depends(update_integration_uc)]
DeleteIntegrationUseCaseDep = Annotated[DeleteIntegrationUseCase, Depends(delete_integration_uc)]


# --- OAuth (Google, Facebook) ---


def get_oauth_authorize_url_uc(
    repo: Annotated[IntegrationRepositoryInterface, Depends(get_integration_repository)],
) -> GetOAuthAuthorizeUrlUseCase:
    return GetOAuthAuthorizeUrlUseCase(repo)


def get_oauth_callback_uc(
    integration_repo: Annotated[IntegrationRepositoryInterface, Depends(get_integration_repository)],
    social_account_repo: Annotated[
        SocialAccountRepositoryInterface, Depends(get_social_account_repository)
    ],
    uow: Annotated[AsyncUserAuthUnitOfWork, Depends(get_unit_of_work)],
    security_utils=Depends(get_security_utils),
) -> OAuthCallbackUseCase:
    return OAuthCallbackUseCase(
        integration_repo, social_account_repo, uow, security_utils
    )


GetOAuthAuthorizeUrlUseCaseDep = Annotated[
    GetOAuthAuthorizeUrlUseCase, Depends(get_oauth_authorize_url_uc)
]
OAuthCallbackUseCaseDep = Annotated[OAuthCallbackUseCase, Depends(get_oauth_callback_uc)]
