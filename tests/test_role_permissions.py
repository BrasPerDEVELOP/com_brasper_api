from app.modules.auth.domain.permissions import ALL_PERMISSIONS, default_permissions_for_role
from app.modules.users.domain.enums import UserRole


def test_default_role_permissions_are_valid() -> None:
    for role in UserRole:
        assert set(default_permissions_for_role(role.value)) <= set(ALL_PERMISSIONS)


def test_world_cup_permissions_were_removed() -> None:
    assert not any(p.startswith("world_cup.") for p in ALL_PERMISSIONS)
