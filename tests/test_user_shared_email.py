from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.users.application.schemas.user_schema import UserCreateCmd
from app.modules.users.application.use_cases.user_use_cases import CreateUserUseCase
from app.modules.auth.application.auth_service import AuthService
from app.modules.auth.application.use_cases.auth_use_cases import CreateAuthUseCase
from app.modules.auth.application.schemas.auth_schema import AuthCreateCmd
from app.modules.integraciones.application.use_cases import oauth_use_cases as oauth
from test_user_phone_area import user_record


@pytest.mark.asyncio
async def test_contact_create_does_not_lookup_or_reuse_email_owner():
    saved = user_record()
    saved.email = 'shared@example.com'
    repo = SimpleNamespace(get_by_email=AsyncMock(side_effect=AssertionError('email no identifica al cliente')),
                           add=AsyncMock(return_value=saved), get=AsyncMock(return_value=saved))
    uow = SimpleNamespace(user_repository=repo, commit=AsyncMock(), rollback=AsyncMock())
    auth = SimpleNamespace(execute=AsyncMock())
    await CreateUserUseCase(uow, auth).execute(UserCreateCmd(email=saved.email, names='Nuevo', role='client'), None)
    new_user = repo.add.await_args.args[0]
    assert new_user.email == saved.email and new_user.auth_id is None
    auth.execute.assert_not_awaited()
    repo.get_by_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_login_username_stays_unique():
    repo = SimpleNamespace(get_by_username=AsyncMock(return_value=object()), create=AsyncMock())
    with pytest.raises(ValueError, match='Username already exists'):
        await CreateAuthUseCase(MagicMock(), repo).execute(AuthCreateCmd(username='shared@example.com', password='Strong123!'))
    repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_assigning_access_never_reuses_another_clients_credentials():
    user = SimpleNamespace(id=uuid4(), auth_id=None, email='shared@example.com')
    users = SimpleNamespace(get_by_id=AsyncMock(return_value=user))
    auth = SimpleNamespace(get_by_username=AsyncMock(return_value=object()), create=AsyncMock())
    security = SimpleNamespace(is_password_strong=lambda value: True, hash_password=lambda value: 'hash')
    uow = SimpleNamespace(user_repository=users, auth_repository=auth)
    with pytest.raises(ValueError, match='ya tiene una cuenta de acceso'):
        await AuthService(uow, security).admin_reset_password(user.id, 'Strong123!')
    auth.create.assert_not_awaited()
    assert user.auth_id is None


@pytest.mark.asyncio
async def test_password_reset_targets_credentials_instead_of_shared_contact():
    credentials = SimpleNamespace(id=uuid4())
    user = SimpleNamespace(id=uuid4(), auth_id=credentials.id)
    users = SimpleNamespace(get_by_email=AsyncMock(side_effect=AssertionError()), get_by_auth_id=AsyncMock(return_value=user))
    auth = SimpleNamespace(get_by_username=AsyncMock(return_value=credentials), update_recovery_code=AsyncMock())
    uow = SimpleNamespace(user_repository=users, auth_repository=auth, commit=AsyncMock())
    security = SimpleNamespace(generate_recovery_code=lambda: 'test-code')
    assert await AuthService(uow, security).generate_password_reset('shared@example.com') == 'test-code'
    auth.update_recovery_code.assert_awaited_once_with(credentials.id, 'test-code')
    users.get_by_email.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('has_credentials', [True, False])
async def test_oauth_shared_email_uses_linked_auth_or_rejects_ambiguity(monkeypatch, has_credentials):
    monkeypatch.setattr(oauth, 'google_exchange_code', AsyncMock(return_value={'access_token': 'test'}))
    monkeypatch.setattr(oauth, 'google_userinfo', AsyncMock(return_value={'id': 'google-id', 'email': 'shared@example.com'}))
    credentials = SimpleNamespace(id=uuid4(), username='shared@example.com')
    user = SimpleNamespace(id=uuid4(), auth_id=credentials.id)
    users = SimpleNamespace(get_by_email=AsyncMock(side_effect=ValueError('varios usuarios')),
        get_by_auth_id=AsyncMock(return_value=user), refresh=AsyncMock())
    auth = SimpleNamespace(get_by_username=AsyncMock(return_value=credentials if has_credentials else None),
        get_by_id=AsyncMock(return_value=credentials), update_token=AsyncMock(), create=AsyncMock())
    integration = SimpleNamespace(get_by_provider=AsyncMock(return_value=SimpleNamespace(
        config={'client_id': 'test', 'client_secret': 'test', 'redirect_uri': 'https://example.com/callback'})))
    social = SimpleNamespace(get_by_provider_and_provider_user_id=AsyncMock(return_value=None), add=AsyncMock())
    uow = SimpleNamespace(user_repository=users, auth_repository=auth, commit=AsyncMock())
    security = SimpleNamespace(generate_opaque_token=lambda **kw: 'test-token')
    uc = oauth.OAuthCallbackUseCase(integration, social, uow, security)
    uc._session_response = AsyncMock(return_value='session')
    if has_credentials:
        assert await uc.execute('google', 'code') == 'session'
        assert social.add.await_args.args[0].user_id == user.id
        users.get_by_email.assert_not_awaited()
    else:
        with pytest.raises(ValueError, match='varios usuarios'):
            await uc.execute('google', 'code')
        social.add.assert_not_awaited()
        auth.create.assert_not_awaited()
