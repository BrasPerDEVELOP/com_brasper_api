# app/modules/integraciones/application/use_cases/oauth_use_cases.py
"""Casos de uso para login OAuth (Google, Facebook)."""
import logging
import secrets
from typing import Optional
from uuid import uuid4

from app.core.security import SecurityUtils
from app.core.unit_of_work import UnitOfWorkBase
from app.modules.auth.domain.credentials import Credentials
from app.modules.auth.application.schemas.auth_schema import TokenInfoDTO, UserInfoDTO
from app.modules.integraciones.application.oauth_providers import (
    google_authorize_url,
    google_exchange_code,
    google_userinfo,
    facebook_authorize_url,
    facebook_exchange_code,
    facebook_userinfo,
)
from app.modules.integraciones.domain.models import Integration, SocialAccount
from app.modules.integraciones.interfaces.integration_repository import IntegrationRepositoryInterface
from app.modules.integraciones.interfaces.social_account_repository import (
    SocialAccountRepositoryInterface,
)

logger = logging.getLogger(__name__)

SUPPORTED_PROVIDERS = ("google", "facebook")


def _config_get(config: Optional[dict], *keys: str, default: str = "") -> str:
    if not config:
        return default
    for k in keys:
        config = config.get(k) if isinstance(config, dict) else None
        if config is None:
            return default
    return str(config)


class GetOAuthAuthorizeUrlUseCase:
    """Genera la URL de autorización para redirigir al usuario a Google o Facebook."""

    def __init__(self, integration_repo: IntegrationRepositoryInterface):
        self.integration_repo = integration_repo

    async def execute(
        self,
        provider: str,
        redirect_uri: Optional[str] = None,
        state: Optional[str] = None,
    ) -> str:
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Proveedor no soportado: {provider}")
        integration = await self.integration_repo.get_by_provider(provider)
        if not integration or not integration.config:
            raise ValueError(f"Integración OAuth no configurada para {provider}")
        config = integration.config
        client_id = _config_get(config, "client_id")
        if not client_id:
            raise ValueError(f"Falta client_id en la configuración de {provider}")
        base_redirect = _config_get(config, "redirect_uri")
        redirect = redirect_uri or base_redirect
        if not redirect:
            raise ValueError(f"Falta redirect_uri para {provider}")
        if provider == "google":
            return google_authorize_url(client_id=client_id, redirect_uri=redirect, state=state)
        if provider == "facebook":
            return facebook_authorize_url(client_id=client_id, redirect_uri=redirect, state=state)
        raise ValueError(f"Proveedor no soportado: {provider}")


class OAuthCallbackUseCase:
    """Intercambia el código por tokens, obtiene datos del usuario del proveedor y crea/vincula usuario y sesión."""

    def __init__(
        self,
        integration_repo: IntegrationRepositoryInterface,
        social_account_repo: SocialAccountRepositoryInterface,
        uow: UnitOfWorkBase,
        security_utils: SecurityUtils,
    ):
        self.integration_repo = integration_repo
        self.social_account_repo = social_account_repo
        self.uow = uow
        self.security_utils = security_utils

    async def execute(
        self,
        provider: str,
        code: str,
        redirect_uri: Optional[str] = None,
    ) -> TokenInfoDTO:
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Proveedor no soportado: {provider}")
        integration = await self.integration_repo.get_by_provider(provider)
        if not integration or not integration.config:
            raise ValueError(f"Integración OAuth no configurada para {provider}")
        config = integration.config
        client_id = _config_get(config, "client_id")
        client_secret = _config_get(config, "client_secret")
        base_redirect = _config_get(config, "redirect_uri")
        redirect = redirect_uri or base_redirect
        if not client_id or not client_secret:
            raise ValueError(f"Configuración incompleta para {provider}")

        if provider == "google":
            token_data = await google_exchange_code(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect,
                code=code,
            )
            access_token = token_data.get("access_token")
            if not access_token:
                raise ValueError("Google no devolvió access_token")
            userinfo = await google_userinfo(access_token)
            provider_user_id = str(userinfo.get("id", ""))
            email = userinfo.get("email") or ""
            name = userinfo.get("name") or ""
            picture_url = userinfo.get("picture")
        else:
            token_data = await facebook_exchange_code(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect,
                code=code,
            )
            access_token = token_data.get("access_token")
            if not access_token:
                raise ValueError("Facebook no devolvió access_token")
            userinfo = await facebook_userinfo(access_token)
            provider_user_id = str(userinfo.get("id", ""))
            email = userinfo.get("email") or ""
            name = userinfo.get("name") or ""
            picture_url = userinfo.get("picture_url")

        # Buscar cuenta social existente
        social = await self.social_account_repo.get_by_provider_and_provider_user_id(
            provider=provider,
            provider_user_id=provider_user_id,
        )
        if social:
            user = await self.uow.user_repository.get(social.user_id)
            if not user:
                raise ValueError("Usuario vinculado no encontrado")
            credentials = await self.uow.auth_repository.get_by_id(user.auth_id)
            if not credentials:
                raise ValueError("Credenciales no encontradas")
            token = self.security_utils.generate_opaque_token(
                user_id=user.id,
                username=credentials.username,
            )
            await self.uow.auth_repository.update_token(credentials.id, token)
            await self.uow.commit()
            return TokenInfoDTO(token=token, user=UserInfoDTO.model_validate(user))

        # Usuario existente por email: vincular cuenta social y opcionalmente crear Auth
        if email:
            existing_user = await self.uow.user_repository.get_by_email(email)
            if existing_user:
                auth_id = existing_user.auth_id
                if not auth_id:
                    username = email.lower()
                    password = secrets.token_urlsafe(32)
                    hashed = self.security_utils.hash_password(password)
                    credentials = Credentials(
                        username=username,
                        password=hashed,
                        recovery_code=None,
                        token=None,
                    )
                    created = await self.uow.auth_repository.create(credentials)
                    auth_id = created.id
                    existing_user.auth_id = auth_id
                    await self.uow.user_repository.update(existing_user)
                social_account = SocialAccount(
                    user_id=existing_user.id,
                    provider=provider,
                    provider_user_id=provider_user_id,
                    email=email,
                    access_token=access_token,
                    refresh_token=token_data.get("refresh_token"),
                )
                await self.social_account_repo.add(social_account)
                credentials = await self.uow.auth_repository.get_by_id(auth_id)
                token = self.security_utils.generate_opaque_token(
                    user_id=existing_user.id,
                    username=credentials.username,
                )
                await self.uow.auth_repository.update_token(auth_id, token)
                await self.uow.commit()
                await self.uow.user_repository.refresh(existing_user)
                return TokenInfoDTO(token=token, user=UserInfoDTO.model_validate(existing_user))

        # Crear usuario nuevo + Auth + SocialAccount
        from app.modules.users.domain.models import User

        username = (email or f"{provider}_{provider_user_id}").lower()
        if not email and await self.uow.auth_repository.get_by_username(username):
            username = f"{provider}_{provider_user_id}_{uuid4().hex[:8]}"
        password = secrets.token_urlsafe(32)
        hashed = self.security_utils.hash_password(password)
        credentials = Credentials(
            username=username,
            password=hashed,
            recovery_code=None,
            token=None,
        )
        created_auth = await self.uow.auth_repository.create(credentials)
        auth_id = created_auth.id
        parts = name.split(None, 1) if name else []
        names = parts[0] if parts else None
        lastnames = parts[1] if len(parts) > 1 else None
        new_user = User(
            auth_id=auth_id,
            email=email or None,
            names=names,
            lastnames=lastnames,
            profile_image=picture_url,
        )
        await self.uow.user_repository.add(new_user)
        social_account = SocialAccount(
            user_id=new_user.id,
            provider=provider,
            provider_user_id=provider_user_id,
            email=email or None,
            access_token=access_token,
            refresh_token=token_data.get("refresh_token"),
        )
        await self.social_account_repo.add(social_account)
        token = self.security_utils.generate_opaque_token(
            user_id=new_user.id,
            username=username,
        )
        await self.uow.auth_repository.update_token(auth_id, token)
        await self.uow.commit()
        await self.uow.user_repository.session.refresh(new_user)
        return TokenInfoDTO(token=token, user=UserInfoDTO.model_validate(new_user))
