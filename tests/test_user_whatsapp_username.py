"""Independent WhatsApp contact: HTTP, persistence and legacy data migration."""
import importlib.util
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.modules.users.application.schemas.user_schema import UserCreateCmd, UserUpdateCmd, UpdateCurrentUserCmd
from app.modules.users.application.use_cases.user_use_cases import CreateUserUseCase, UpdateUserUseCase
from app.modules.users.domain.models import User


@pytest.fixture
def client():
    app = FastAPI()

    @app.post('/user')
    def create(form=Depends(UserCreateCmd.from_form)):
        return form[0].model_dump(mode='json', exclude_unset=True)

    @app.put('/user')
    def update(form=Depends(UserUpdateCmd.from_form)):
        return form[0].model_dump(mode='json', exclude_unset=True)

    @app.put('/auth/me')
    def profile(cmd: UpdateCurrentUserCmd):
        return cmd.model_dump(exclude_unset=True)

    return TestClient(app)


@pytest.mark.parametrize('method', ['post', 'put'])
def test_form_keeps_phone_and_username_separate(client, method):
    response = client.request(method, '/user', files={
        'id': (None, str(uuid4())), 'phone': (None, '001234567'),
        'whatsapp_username': (None, ' @cliente '),
    })
    assert response.status_code == 200, response.text
    assert response.json()['phone'] == '001234567'
    assert response.json()['whatsapp_username'] == '@cliente'


def test_partial_update_preserves_omitted_username_and_supports_explicit_clear(client):
    data = {'id': str(uuid4()), 'names': 'Nombre'}
    assert 'whatsapp_username' not in client.put('/user', data=data).json()
    response = client.put('/user', data={**data, 'whatsapp_username': '', 'clear_whatsapp_username': 'true'})
    assert response.status_code == 200, response.text
    assert response.json()['whatsapp_username'] is None
    assert client.put('/auth/me', json={'whatsapp_username': None}).json() == {'whatsapp_username': None}
    assert client.post('/user', data={'whatsapp_username': 'x' * 101}).status_code == 422


async def test_create_update_and_clear_persist_independent_contacts():
    saved = User(id=uuid4(), created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
                 identifications=[], permissions_granted=[], permissions_revoked=[])
    uow = MagicMock()

    async def add(user):
        saved.phone = user.phone
        saved.whatsapp_username = user.whatsapp_username
        return saved

    uow.user_repository.add = AsyncMock(side_effect=add)
    uow.user_repository.get = AsyncMock(return_value=saved)
    uow.user_repository.update = AsyncMock(side_effect=lambda user: user)
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    created = await CreateUserUseCase(uow, AsyncMock()).execute(
        UserCreateCmd(phone='001234567', whatsapp_username=' @cliente '), None)
    assert created.whatsapp_username == saved.whatsapp_username == '@cliente'
    assert created.phone == saved.phone == '001234567'
    update = UpdateUserUseCase(uow)
    await update.execute(UserUpdateCmd(id=saved.id, names='Otro'))
    assert saved.whatsapp_username == '@cliente'
    changed = await update.execute(UserUpdateCmd(id=saved.id, whatsapp_username='@nuevo'))
    assert changed.whatsapp_username == '@nuevo'
    await update.execute(UserUpdateCmd(id=saved.id, whatsapp_username=None))
    assert saved.whatsapp_username is None
    assert saved.phone == '001234567'


def test_migration_copies_handles_without_touching_phone_or_other_users():
    path = Path(__file__).parents[1] / 'app/db/migrations/versions/2026_11_26_1300_00-101_user_whatsapp_username.py'
    spec = importlib.util.spec_from_file_location('migration_101', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine('sqlite://')
    with engine.begin() as conn:
        conn.connection.driver_connection.create_function('btrim', 1, lambda value: value.strip() if value else value)
        conn.exec_driver_sql("ATTACH DATABASE ':memory:' AS user")
        conn.exec_driver_sql('CREATE TABLE "user"."user" (id INTEGER PRIMARY KEY, phone VARCHAR(100))')
        conn.exec_driver_sql('INSERT INTO "user"."user" VALUES (1, ?), (2, ?), (3, NULL)', (' @cliente ', '001234567'))
        migration.op = Operations(MigrationContext.configure(conn))
        migration.upgrade()
        rows = conn.execute(sa.text('SELECT phone, whatsapp_username FROM "user"."user" ORDER BY id')).all()
        assert rows == [(' @cliente ', '@cliente'), ('001234567', None), (None, None)]


@pytest.mark.parametrize('raw,expected', [('cliente', '@cliente'), ('@@cliente', '@cliente'), ('@', None), (' ', None)])
def test_default_prefix_is_normalized(raw, expected):
    assert UserCreateCmd(whatsapp_username=raw).whatsapp_username == expected
    assert UpdateCurrentUserCmd(whatsapp_username=raw).whatsapp_username == expected
