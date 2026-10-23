import inspect
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.users.application.schemas.user_schema import (
    UserCreateCmd, UserUpdateCmd, UpdateCurrentUserCmd,
    UserReadDTO, UserReadGeneralDTO,
)
from app.modules.users.application.use_cases.user_use_cases import (
    CreateUserUseCase, UpdateUserUseCase,
)
from app.modules.users.domain.models import User
from app.modules.auth.application.schemas.auth_schema import UserInfoDTO


def user_record(**kwargs):
    return User(id=uuid4(), created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc), identifications=[],
                permissions_granted=[], permissions_revoked=[], **kwargs)


def form_cmd(cls, **values):
    args = {key: None for key in inspect.signature(cls.from_form).parameters}
    args.update(values)
    return cls.from_form(**args)[0]


@pytest.mark.parametrize('cls', [UserCreateCmd, UserUpdateCmd, UpdateCurrentUserCmd])
def test_area_accepts_text_codes_and_normalizes_input(cls):
    values = dict(local_area_code=' 011 ', local_area_name=' São Paulo ', country=' Brasil ')
    if cls is UserUpdateCmd:
        values['id'] = uuid4()
    cmd = cls(**values)
    assert (cmd.local_area_code, cmd.local_area_name, cmd.country) == ('011', 'São Paulo', 'Brasil')
    with pytest.raises(ValidationError):
        cls(**{**values, 'local_area_code': '+55'})
    with pytest.raises(ValidationError):
        cls(**{**values, 'local_area_code': '1234567'})


def test_form_preserves_omitted_fields_and_can_clear_with_whitespace():
    omitted = form_cmd(UserUpdateCmd, id=str(uuid4()), names='Nombre nuevo')
    assert not {'local_area_code', 'local_area_name', 'country'} & omitted.model_fields_set
    cleared = form_cmd(UserUpdateCmd, id=str(uuid4()), local_area_code=' ', country=' ')
    assert cleared.local_area_code is None and cleared.country is None
    assert {'local_area_code', 'country'} <= cleared.model_fields_set


def test_create_form_and_read_dtos_expose_area():
    cmd = form_cmd(UserCreateCmd, local_area_code='11', local_area_name='São Paulo', country='Brasil')
    user = user_record(local_area_code=cmd.local_area_code, local_area_name=cmd.local_area_name, country=cmd.country)
    for dto in (UserReadDTO, UserReadGeneralDTO, UserInfoDTO):
        result = dto.model_validate(user).model_dump()
        assert result['local_area_code'] == '11'
        assert result['local_area_name'] == 'São Paulo'
        assert result['country'] == 'Brasil'


@pytest.mark.asyncio
async def test_update_persists_area_preserves_omissions_and_clears_null():
    user = user_record(local_area_code='11', local_area_name='São Paulo', country='Brasil')
    uow = MagicMock()
    uow.user_repository.get = AsyncMock(return_value=user)
    uow.user_repository.update = AsyncMock(side_effect=lambda obj: obj)
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    uc = UpdateUserUseCase(uow)
    await uc.execute(UserUpdateCmd(id=user.id, names='Nuevo nombre'))
    assert user.local_area_code == '11' and user.country == 'Brasil'
    result = await uc.execute(UserUpdateCmd(id=user.id, local_area_code='21', local_area_name='Rio de Janeiro'))
    assert result.local_area_code == '21' and user.local_area_name == 'Rio de Janeiro'
    await uc.execute(UserUpdateCmd(id=user.id, local_area_code=None, local_area_name=None, country=None))
    assert (user.local_area_code, user.local_area_name, user.country) == (None, None, None)


@pytest.mark.asyncio
async def test_create_persists_phone_area():
    saved = user_record()
    async def add(user):
        for key in ('local_area_code', 'local_area_name', 'country'):
            setattr(saved, key, getattr(user, key))
        return saved
    uow = MagicMock()
    uow.user_repository.add = AsyncMock(side_effect=add)
    uow.user_repository.get = AsyncMock(return_value=saved)
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    result = await CreateUserUseCase(uow, AsyncMock()).execute(
        UserCreateCmd(local_area_code='11', local_area_name='São Paulo', country='Brasil'), None,
    )
    assert (result.local_area_code, result.local_area_name, result.country) == ('11', 'São Paulo', 'Brasil')


def test_openapi_exposes_area_on_user_forms():
    from app.main import app
    schema = app.openapi()
    for path in ('/user', '/user/'):
        if path not in schema['paths']:
            continue
        for verb in ('post', 'put'):
            body = schema['paths'][path][verb]['requestBody']['content']['multipart/form-data']['schema']
            properties = schema['components']['schemas'][body['$ref'].split('/')[-1]]['properties']
            assert {'local_area_code', 'local_area_name', 'country'} <= properties.keys()
        break
    else:
        pytest.fail('No user route found')
