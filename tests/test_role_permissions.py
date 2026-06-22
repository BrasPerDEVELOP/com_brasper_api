from app.modules.auth.domain.permissions import ALL_PERMISSIONS, default_permissions_for_role


WORLD_CUP_PERMISSIONS = {
    "world_cup.view",
    "world_cup.manage",
    "world_cup.approve",
}


def test_world_cup_permissions_are_valid_role_permissions() -> None:
    assert WORLD_CUP_PERMISSIONS <= set(ALL_PERMISSIONS)


def test_marketing_role_gets_world_cup_permissions_by_default() -> None:
    assert WORLD_CUP_PERMISSIONS <= set(default_permissions_for_role("marketing"))
