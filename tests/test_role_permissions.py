from app.modules.auth.domain.permissions import ALL_PERMISSIONS, default_permissions_for_role
from app.modules.users.domain.enums import UserRole


def test_default_role_permissions_are_valid() -> None:
    for role in UserRole:
        assert set(default_permissions_for_role(role.value)) <= set(ALL_PERMISSIONS)


def test_world_cup_permissions_were_removed() -> None:
    assert not any(p.startswith("world_cup.") for p in ALL_PERMISSIONS)


class TestTagPermissions:
    """Los permisos del catálogo de etiquetas tienen que existir en el backend.

    El front los ofrecía en la pantalla de roles, pero el validador del API los
    rechazaba con 422 («Permisos inválidos: tags.view, ...») porque solo estaban
    en el catálogo del front.
    """

    def test_los_cuatro_permisos_existen(self):
        from app.modules.auth.domain.permissions import ALL_PERMISSIONS

        for permission in ("tags.view", "tags.create", "tags.update", "tags.delete"):
            assert permission in ALL_PERMISSIONS

    def test_el_validador_de_roles_los_acepta(self):
        from app.modules.users.adapters.router.role_permission_routes import (
            RolePermissionsUpdateRequest,
        )

        request = RolePermissionsUpdateRequest(
            permissions=["transactions.view", "tags.view", "tags.create"]
        )
        assert "tags.view" in request.permissions

    def test_ventas_puede_aplicar_etiquetas_pero_no_administrarlas(self):
        from app.modules.auth.domain.permissions import DEFAULT_ROLE_PERMISSIONS

        sales = DEFAULT_ROLE_PERMISSIONS["sales"]
        assert "tags.view" in sales
        assert "tags.create" not in sales
        assert "tags.delete" not in sales

    def test_admin_los_tiene_todos(self):
        from app.modules.auth.domain.permissions import DEFAULT_ROLE_PERMISSIONS

        admin = DEFAULT_ROLE_PERMISSIONS["admin"]
        for permission in ("tags.view", "tags.create", "tags.update", "tags.delete"):
            assert permission in admin
