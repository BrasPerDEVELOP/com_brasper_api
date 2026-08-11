from __future__ import annotations

from typing import Iterable

from app.modules.users.domain.enums import UserRole


PERMISSION_MODULES: tuple[dict[str, object], ...] = (
    {"key": "dashboard", "permissions": ("dashboard.view",)},
    {"key": "metrics", "permissions": ("metrics.view",)},
    {
        "key": "users",
        "permissions": (
            "users.view",
            "users.create",
            "users.update",
            "users.delete",
            "users.reset_password",
        ),
    },
    {
        "key": "roles.permissions",
        "permissions": ("roles.permissions.view", "roles.permissions.update"),
    },
    {
        "key": "transactions",
        "permissions": (
            "transactions.view",
            "transactions.create",
            "transactions.update",
            "transactions.delete",
        ),
    },
    {"key": "accounting", "permissions": ("accounting.view",)},
    {"key": "calculator", "permissions": ("calculator.view",)},
    {
        "key": "coupons",
        "permissions": (
            "coupons.view",
            "coupons.create",
            "coupons.update",
            "coupons.delete",
        ),
    },
    {
        "key": "bank_accounts",
        "permissions": (
            "bank_accounts.view",
            "bank_accounts.create",
            "bank_accounts.update",
            "bank_accounts.delete",
        ),
    },
    {
        "key": "company_bank_accounts",
        "permissions": (
            "company_bank_accounts.view",
            "company_bank_accounts.create",
            "company_bank_accounts.update",
            "company_bank_accounts.delete",
        ),
    },
    {
        "key": "commissions",
        "permissions": (
            "commissions.view",
            "commissions.create",
            "commissions.update",
            "commissions.delete",
        ),
    },
    {
        "key": "rates",
        "permissions": ("rates.view", "rates.create", "rates.update", "rates.delete"),
    },
    {
        "key": "tags",
        "permissions": ("tags.view", "tags.create", "tags.update", "tags.delete"),
    },
    {"key": "home_banner", "permissions": ("home_banner.view", "home_banner.update")},
    {"key": "audit", "permissions": ("audit.view",)},
    {"key": "contact_forms", "permissions": ("contact_forms.view",)},
    {
        "key": "integrations",
        "permissions": (
            "integrations.view",
            "integrations.create",
            "integrations.update",
            "integrations.delete",
        ),
    },
    {
        "key": "blog",
        "permissions": (
            "blog.view",
            "blog.create",
            "blog.update",
            "blog.delete",
        ),
    },
    {
        "key": "profile",
        "permissions": (
            "profile.view",
            "profile.update",
            "profile.change_password",
        ),
    },
)

ALL_PERMISSIONS: tuple[str, ...] = tuple(
    permission
    for module in PERMISSION_MODULES
    for permission in module["permissions"]  # type: ignore[index]
)

DEFAULT_ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    UserRole.admin.value: ALL_PERMISSIONS,
    UserRole.client.value: (
        "dashboard.view",
        "calculator.view",
        "profile.view",
        "profile.update",
        "profile.change_password",
    ),
    UserRole.sales.value: (
        "dashboard.view",
        "metrics.view",
        "users.view",
        "users.create",
        "users.update",
        "bank_accounts.view",
        "bank_accounts.create",
        "bank_accounts.update",
        "transactions.view",
        "transactions.create",
        "transactions.update",
        "tags.view",
        "calculator.view",
        "coupons.view",
        "coupons.create",
        "coupons.update",
        "profile.view",
        "profile.update",
        "profile.change_password",
    ),
    UserRole.accounting.value: (
        "dashboard.view",
        "metrics.view",
        "accounting.view",
        "transactions.view",
        "bank_accounts.view",
        "profile.view",
        "profile.update",
        "profile.change_password",
    ),
    UserRole.marketing.value: (
        "dashboard.view",
        "coupons.view",
        "coupons.create",
        "coupons.update",
        "home_banner.view",
        "home_banner.update",
        "blog.view",
        "blog.create",
        "blog.update",
        "blog.delete",
        "profile.view",
        "profile.update",
        "profile.change_password",
    ),
    UserRole.user.value: (
        "dashboard.view",
        "profile.view",
        "profile.update",
        "profile.change_password",
    ),
}


def normalize_permissions(permissions: Iterable[str] | None, role: str | None = None) -> list[str]:
    allowed = set(ALL_PERMISSIONS)
    parsed = [p for p in permissions or [] if p in allowed]
    if parsed:
        return parsed
    return list(DEFAULT_ROLE_PERMISSIONS.get(role or "", DEFAULT_ROLE_PERMISSIONS[UserRole.user.value]))


def default_permissions_for_role(role: str | None) -> list[str]:
    return list(DEFAULT_ROLE_PERMISSIONS.get(role or "", DEFAULT_ROLE_PERMISSIONS[UserRole.user.value]))
