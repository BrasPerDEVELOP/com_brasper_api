# app/core/containers
# Inyección de dependencias por módulo: common, auth, users, coin.
from app.core.containers.common import get_security_utils
from app.core.containers.auth import get_auth_repository, get_login_uc, get_auth_service
from app.core.containers.unit_of_work import get_unit_of_work
from app.core.containers.users import (
    get_user_repository,
    get_user_by_id_uc,
    get_user_by_email_uc,
    get_user_by_auth_id_uc,
    create_user_uc,
    list_user_name_uc,
    list_users_uc,
    list_users_with_details_uc,
    update_user_uc,
    delete_user_uc,
)
from app.core.containers.coin import (
    get_tax_rate_repository,
    get_commission_repository,
    get_tax_rate_by_id_uc,
    list_tax_rates_uc,
    create_tax_rate_uc,
    update_tax_rate_uc,
    delete_tax_rate_uc,
    get_commission_by_id_uc,
    list_commissions_uc,
    create_commission_uc,
    update_commission_uc,
    delete_commission_uc,
)

__all__ = [
    "get_security_utils",
    "get_auth_repository",
    "get_login_uc",
    "get_auth_service",
    "get_unit_of_work",
    "get_user_repository",
    "get_user_by_id_uc",
    "get_user_by_email_uc",
    "get_user_by_auth_id_uc",
    "create_user_uc",
    "list_user_name_uc",
    "list_users_uc",
    "list_users_with_details_uc",
    "update_user_uc",
    "delete_user_uc",
    "get_tax_rate_repository",
    "get_commission_repository",
    "get_tax_rate_by_id_uc",
    "list_tax_rates_uc",
    "create_tax_rate_uc",
    "update_tax_rate_uc",
    "delete_tax_rate_uc",
    "get_commission_by_id_uc",
    "list_commissions_uc",
    "create_commission_uc",
    "update_commission_uc",
    "delete_commission_uc",
]
