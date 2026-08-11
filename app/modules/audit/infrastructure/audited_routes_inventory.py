# app/modules/audit/infrastructure/audited_routes_inventory.py
"""
Inventario exacto de todas las rutas mutables (POST, PUT, PATCH, DELETE) canónicas montadas en FastAPI.
Coincide 1:1 con los paths reales expuestos en OpenAPI de main_app.
Excluye explícitamente GETs y /auth/login, /auth/refresh, /auth/logout que están cubiertas por su propio flujo de auditoría de auth.
"""

AUDITED_MUTATION_ROUTES = {
    # Users & Roles
    ("POST", "/user"),
    ("PUT", "/user"),
    ("DELETE", "/user/{user_id}"),
    ("POST", "/user/{user_id}/reset-password"),
    ("PUT", "/roles/{role}/permissions"),

    # Auth profile & reset
    ("POST", "/auth/me"),
    ("PUT", "/auth/me"),
    ("POST", "/auth/me/profile-image"),
    ("POST", "/auth/change-password"),
    ("POST", "/auth/reset-password"),
    ("POST", "/auth/reset-password/confirm"),

    # Transactions & sub-routers (con prefijo /transactions registrado en main.py)
    ("POST", "/transactions/import"),
    ("POST", "/transactions"),
    ("PUT", "/transactions"),
    ("DELETE", "/transactions/{transaction_id}"),
    ("POST", "/transactions/banks"),
    ("PUT", "/transactions/banks"),
    ("DELETE", "/transactions/banks/{bank_id}"),
    ("POST", "/transactions/bank-accounts"),
    ("PUT", "/transactions/bank-accounts"),
    ("DELETE", "/transactions/bank-accounts/{bank_account_id}"),
    ("POST", "/transactions/tags"),
    ("PUT", "/transactions/tags"),
    ("DELETE", "/transactions/tags/{tag_id}"),
    ("POST", "/transactions/coupons"),
    ("PUT", "/transactions/coupons"),
    ("DELETE", "/transactions/coupons/{coupon_id}"),

    # Coin / Tax Rates / Commissions (con prefijo /coin registrado en main.py)
    ("POST", "/coin/tax-rate"),
    ("PUT", "/coin/tax-rate"),
    ("DELETE", "/coin/tax-rate/{tax_rate_id}"),
    ("POST", "/coin/tax-rate-trial"),
    ("PUT", "/coin/tax-rate-trial"),
    ("DELETE", "/coin/tax-rate-trial/{tax_rate_trial_id}"),
    ("POST", "/coin/commission"),
    ("PUT", "/coin/commission"),
    ("DELETE", "/coin/commission/{commission_id}"),
    ("POST", "/coin/commission-trial"),
    ("PUT", "/coin/commission-trial"),
    ("DELETE", "/coin/commission-trial/{commission_trial_id}"),

    # Blog (con prefijo /blog)
    ("POST", "/blog"),
    ("PUT", "/blog"),
    ("DELETE", "/blog/{blog_id}"),

    # Home Image (con prefijo /home-banner registrado en main.py)
    ("POST", "/home-banner/home-image"),
    ("PUT", "/home-banner/home-image"),
    ("POST", "/home-banner/home-popup"),
    ("PUT", "/home-banner/home-popup"),

    # Integraciones (con prefijo /integraciones registrado en main.py)
    ("POST", "/integraciones/integration"),
    ("PUT", "/integraciones/integration"),
    ("DELETE", "/integraciones/integration/{integration_id}"),

    # Brasper Public / AI (con prefijo /brasper registrado en main.py)
    ("POST", "/brasper/contact-form"),
    ("POST", "/brasper/ai/clients/upsert"),
}
