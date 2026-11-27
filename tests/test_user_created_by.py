from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.base import get_db
from app.core.container import create_user_uc
from app.modules.auth.infrastructure.dependencies import authorize_user_creation, get_optional_current_user
from app.modules.users.adapters.router.user_routes import router
from app.modules.users.application.schemas.user_schema import UserCreateCmd, UserUpdateCmd
from app.modules.users.application.use_cases.user_use_cases import CreateUserUseCase, UpdateUserUseCase
from app.modules.users.domain.models import User


def user_record():
    return User(id=uuid4(), names='Cliente', created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc), identifications=[],
                permissions_granted=[], permissions_revoked=[])


@pytest.mark.parametrize('internal', [True, False])
@pytest.mark.parametrize('path', ['/user', '/user/'])
def test_post_uses_authenticated_creator_and_ignores_submitted_creator(internal, path):
    app = FastAPI()
    app.include_router(router)
    creator = str(uuid4())
    saved = user_record()
    saved.created_by = creator if internal else None
    uc = SimpleNamespace(execute=AsyncMock(return_value=saved))
    app.dependency_overrides[create_user_uc] = lambda: uc
    app.dependency_overrides[authorize_user_creation] = lambda: internal
    app.dependency_overrides[get_optional_current_user] = lambda: {'user_id': creator} if internal else {}
    app.dependency_overrides[get_db] = lambda: None
    for route in router.routes:
        for dep in getattr(getattr(route, 'dependant', None), 'dependencies', []):
            if getattr(dep.call, '__audit_dependency__', False):
                app.dependency_overrides[dep.call] = lambda: None
    response = TestClient(app).post(path, data={
        'names': 'Cliente', 'email': 'cliente@example.com', 'password': 'Strong123!',
        'created_by': str(uuid4()),
    })
    assert response.status_code == 201, response.text
    expected = creator if internal else None
    assert uc.execute.await_args.kwargs == {'created_by': expected}
    assert response.json()['created_by'] == expected
    assert 'created_by' not in uc.execute.await_args.args[0].model_dump()


@pytest.mark.parametrize('creator', [None, str(uuid4())])
async def test_creator_is_persisted_before_commit_and_unchanged_on_update(creator):
    saved = user_record()
    uow = MagicMock()

    async def add(entity):
        saved.created_by = entity.created_by
        return saved

    uow.user_repository.add = AsyncMock(side_effect=add)
    uow.user_repository.get = AsyncMock(return_value=saved)
    uow.user_repository.update = AsyncMock(return_value=saved)
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    result = await CreateUserUseCase(uow, AsyncMock()).execute(UserCreateCmd(names='Cliente'), None, created_by=creator)
    assert uow.user_repository.add.await_args.args[0].created_by == creator
    assert result.created_by == creator
    # Editing an existing profile must never replace its original creator.
    await UpdateUserUseCase(uow).execute(UserUpdateCmd(id=saved.id, names='Nombre corregido', created_by='forged'))
    assert saved.created_by == creator
