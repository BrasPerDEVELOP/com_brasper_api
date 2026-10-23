from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.modules.users.infrastructure.repository import SQLAlchemyUserRepository
from app.modules.users.application.use_cases.user_use_cases import ListUserUseCase


@pytest.mark.asyncio
async def test_list_use_case_forwards_all_filters_to_repository():
    repo = AsyncMock()
    repo.list_filtered.return_value = []
    user_id = uuid4()
    assert await ListUserUseCase(repo).execute(user_id=user_id, role='client', country='brasil', search='Ana') == []
    repo.list_filtered.assert_awaited_once_with(user_id=user_id, role='client', country='brasil', search='Ana')
    repo.list.assert_not_called()


@pytest.mark.asyncio
async def test_repository_combines_country_role_search_and_excludes_deleted():
    from unittest.mock import MagicMock
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db.execute.return_value = result
    repo = SQLAlchemyUserRepository(db)
    await repo.list_filtered(role='client', country='Perú', search='Ana%_')
    statement = db.execute.call_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert 'translate' in sql and 'EXISTS' in sql
    assert 'deleted IS false' in sql
    assert 'peru' in compiled.params.values()
    assert 'Ana/%/_' in compiled.params.values()


def test_openapi_documents_filter_contract():
    from app.main import app
    paths = app.openapi()['paths']
    path = '/user' if '/user' in paths else '/user/'
    assert {'country', 'search', 'role'} <= {p['name'] for p in paths[path]['get']['parameters']}
    assert '/user/filter-options' in paths or '/user/filter-options/' in paths
