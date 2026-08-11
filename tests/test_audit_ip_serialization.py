"""
Las columnas `ip_address` de auditoría son INET, así que el driver devuelve
objetos `IPv4Address`/`IPv6Address`. Los DTOs declaraban `str` y rechazaban ese
valor, de modo que GET /audit/events respondía 422 y la bitácora completa
quedaba inaccesible.
"""
from datetime import datetime, timezone
from ipaddress import IPv4Address, IPv6Address
from uuid import uuid4

import pytest

from app.modules.audit.adapters.router.audit_routes import (
    AuditEventDTO,
    AuditEventSummaryDTO,
    LoginEventDTO,
)


class _Row:
    """Fila tal como la entrega SQLAlchemy, con la IP ya convertida por el driver."""

    def __init__(self, ip):
        self.id = uuid4()
        self.actor_user_id = None
        self.actor_username = "admin@brasper.com"
        self.actor_role = "admin"
        self.action = "user.delete"
        self.entity = "user"
        self.entity_id = str(uuid4())
        self.description = None
        self.old_values = None
        self.new_values = None
        self.source = "backoffice"
        self.ip_address = ip
        self.user_agent = None
        self.method = "DELETE"
        self.path = "/user/1"
        self.status_code = 204
        self.request_id = uuid4()
        self.success = True
        self.meta_data = None
        self.created_at = datetime.now(timezone.utc)
        # Campos propios de login_event
        self.user_id = None
        self.attempted_username = None
        self.failure_reason = None
        self.browser = None
        self.os = None
        self.device = None
        self.session_id = None


@pytest.mark.parametrize("dto", [AuditEventDTO, AuditEventSummaryDTO, LoginEventDTO])
@pytest.mark.parametrize(
    "ip,esperado",
    [
        (IPv4Address("45.177.196.205"), "45.177.196.205"),
        (IPv6Address("2001:db8::1"), "2001:db8::1"),
        ("45.177.196.205", "45.177.196.205"),
        (None, None),
    ],
)
def test_ip_address_se_serializa_como_cadena(dto, ip, esperado):
    assert dto.model_validate(_Row(ip)).ip_address == esperado
