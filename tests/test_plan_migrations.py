import importlib.util
from pathlib import Path
from unittest.mock import MagicMock
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql
from app.modules.notifications.models import Notification
from app.modules.users.domain.models import User


def test_notifications_ddl_and_user_deltas_compile_for_postgresql():
    dialect = postgresql.dialect()
    assert 'recipient_user_id' in str(CreateTable(Notification.__table__).compile(dialect=dialect))
    ddl = str(CreateTable(User.__table__).compile(dialect=dialect))
    assert 'permissions_granted JSONB' in ddl
    assert 'permissions_revoked JSONB' in ddl


def test_plan_migrations_upgrade_and_downgrade_operations(monkeypatch):
    root = Path(__file__).resolve().parents[1] / 'app/db/migrations/versions'
    for revision, parent in [('079', '078'), ('080', '079')]:
        path = next(root.glob(f'*-{revision}_*.py'))
        spec = importlib.util.spec_from_file_location(f'migration_{revision}', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        operations = MagicMock()
        monkeypatch.setattr(module, 'op', operations)
        assert module.down_revision == parent
        module.upgrade()
        assert operations.add_column.called
        module.downgrade()
        assert operations.drop_column.called
