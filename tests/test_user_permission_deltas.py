from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.modules.auth.domain.permissions import effective_permissions, validate_permission_deltas, ALL_PERMISSIONS
from app.modules.auth.infrastructure.dependencies import _load_permissions
from app.modules.users.application.permission_overrides import validate_user_access_change
from app.modules.users.application.schemas.user_schema import UserUpdateCmd
from app.modules.auth.domain.permissions import GUARANTEED_ROLE_PERMISSIONS


def test_guaranteed_contract_matches_frontend_snapshot():
    assert GUARANTEED_ROLE_PERMISSIONS == {'accounting': ('accounting.view',)}


def test_access_only_form_does_not_erase_profile_fields():
    cmd, _ = UserUpdateCmd.from_form(id=str(uuid4()), names=None, lastnames=None,
        email=None, profile_image=None, document_number=None, document_type=None,
        identifications=None, permissions_granted='["blog.view"]', permissions_revoked='[]',
        is_agent=None, role=None, phone=None, code_phone=None)
    assert cmd.model_fields_set == {'id', 'permissions_granted', 'permissions_revoked'}


def test_grant_revoke_and_live_role_inheritance():
    assert effective_permissions('sales', ['coupons.create'], ['blog.view'], ['coupons.create']) == ['blog.view']
    assert effective_permissions('sales', ['coupons.create', 'users.view'], ['blog.view'], ['coupons.create']) == ['blog.view', 'users.view']


def test_empty_matrix_and_guaranteed_permissions():
    assert effective_permissions('sales', []) == []
    assert effective_permissions('accounting', [], [], ['accounting.view']) == ['accounting.view']
    assert effective_permissions('admin', [], [], ALL_PERMISSIONS) == sorted(ALL_PERMISSIONS)


@pytest.mark.parametrize('role,granted,revoked', [
    ('client', ['blog.view'], []), ('admin', ['blog.view'], []),
    ('sales', ['unknown.view'], []), ('sales', ['blog.view'], ['blog.view']),
    ('accounting', [], ['accounting.view']),
])
def test_invalid_deltas(role, granted, revoked):
    with pytest.raises(ValueError):
        validate_permission_deltas(role, granted, revoked)


def test_self_edit_and_missing_permission_are_forbidden():
    uid = uuid4()
    previous = SimpleNamespace(id=uid, role='sales', permissions_granted=[], permissions_revoked=[])
    cmd = UserUpdateCmd(id=uid, permissions_granted=['blog.view'])
    for actor, permissions in [(uid, ['users.update', 'roles.permissions.update']), (uuid4(), ['users.update'])]:
        with pytest.raises(HTTPException) as exc:
            validate_user_access_change(cmd, previous, actor, permissions)
        assert exc.value.status_code == 403


async def test_database_resolver_applies_user_deltas():
    user = SimpleNamespace(role='sales', permissions_granted=['blog.view'], permissions_revoked=['coupons.create'])
    results = []
    for value in (user, SimpleNamespace(permissions=['coupons.create'])):
        result = MagicMock()
        result.scalar_one_or_none.return_value = value
        results.append(result)
    db = SimpleNamespace(execute=AsyncMock(side_effect=results))
    assert await _load_permissions({'user_id': str(uuid4())}, db) == ['blog.view']
