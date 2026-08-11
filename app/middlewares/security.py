import ipaddress
import logging
import re
import threading
import time
import uuid
from typing import Dict, List, Tuple
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.settings import get_settings

logger = logging.getLogger(__name__)

# En-memory store concurrente y acotado para rate limiting: (ip, scope) -> list de timestamps
_rate_limit_lock = threading.Lock()
_rate_limit_store: Dict[Tuple[str, str], List[float]] = {}
_MAX_STORE_ENTRIES = 10000

UUID_REGEX = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)


def resolve_client_ip(request: Request) -> str:
    """
    Resuelve la IP del cliente de forma segura.
    Confía en X-Forwarded-For solo si el peer inmediato (request.client.host)
    pertenece a TRUSTED_PROXY_CIDRS.
    Valida las IP en X-Forwarded-For de derecha a izquierda (cadena de proxies) y extrae la IP cliente.
    """
    settings = get_settings()
    peer_ip_str = request.client.host if request.client else "127.0.0.1"

    try:
        peer_ip = ipaddress.ip_address(peer_ip_str)
    except ValueError:
        return peer_ip_str

    trusted_networks = []
    for cidr in settings.TRUSTED_PROXY_CIDRS:
        try:
            trusted_networks.append(ipaddress.ip_network(cidr, strict=False))
        except ValueError:
            continue

    def is_trusted(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
        return any(address in network for network in trusted_networks)

    if is_trusted(peer_ip):
        xff = request.headers.get("X-Forwarded-For")
        if xff:
            raw_ips = [ip.strip() for ip in xff.split(",") if ip.strip()]
            valid_ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
            for ip_s in raw_ips:
                try:
                    valid_ips.append(ipaddress.ip_address(ip_s))
                except ValueError:
                    return peer_ip_str
            for address in reversed(valid_ips):
                if not is_trusted(address):
                    return str(address)
            if valid_ips:
                return str(valid_ips[0])

    return peer_ip_str


def check_rate_limit(ip: str, scope: str, max_requests: int, window_seconds: int = 60) -> bool:
    """
    Comprueba de forma concurrente y acotada si se superó el límite de peticiones.
    Retorna True si está permitido, False si excedió el límite.
    """
    now = time.time()
    key = (ip, scope)
    cutoff = now - window_seconds

    with _rate_limit_lock:
        # Limpieza periódica si la memoria excede el límite acotado
        if len(_rate_limit_store) >= _MAX_STORE_ENTRIES and key not in _rate_limit_store:
            stale_keys = [
                k for k, ts in _rate_limit_store.items()
                if not ts or ts[-1] <= cutoff
            ]
            for k in stale_keys:
                del _rate_limit_store[k]
            if len(_rate_limit_store) >= _MAX_STORE_ENTRIES:
                oldest_key = min(
                    _rate_limit_store,
                    key=lambda item: _rate_limit_store[item][-1] if _rate_limit_store[item] else 0,
                )
                del _rate_limit_store[oldest_key]

        timestamps = _rate_limit_store.get(key, [])
        valid_timestamps = [t for t in timestamps if t > cutoff]

        if len(valid_timestamps) >= max_requests:
            _rate_limit_store[key] = valid_timestamps
            return False

        valid_timestamps.append(now)
        _rate_limit_store[key] = valid_timestamps
        return True


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware que asigna Request ID (X-Request-ID) verificado/generado como UUID v4
    y resuelve la IP segura.
    """
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        header_name = settings.REQUEST_ID_HEADER
        client_req_id = request.headers.get(header_name)

        if client_req_id and UUID_REGEX.match(client_req_id):
            request_id = client_req_id
        else:
            request_id = str(uuid.uuid4())

        client_ip = resolve_client_ip(request)
        request.state.request_id = request_id
        request.state.client_ip = client_ip

        # Evaluar Rate Limit para endpoints sensibles
        # Rechazar inmediatamente si se usa path ambiguo o codificado
        path = request.url.path
        method = request.method.upper()

        # Sanidad de path en rate-limiting
        norm_path = path.rstrip("/") or "/"

        if method == "POST":
            limit = None
            scope = None
            if norm_path == "/auth/login":
                limit = settings.RATE_LIMIT_LOGIN
                scope = "login"
            elif norm_path == "/user":
                limit = settings.RATE_LIMIT_REGISTER
                scope = "register"
            elif norm_path in ("/auth/reset-password", "/auth/reset-password/confirm"):
                limit = settings.RATE_LIMIT_PASSWORD_RESET
                scope = "reset_password"
            elif norm_path == "/brasper/contact-form":
                limit = settings.RATE_LIMIT_CONTACT_FORM
                scope = "contact_form"

            if limit and scope:
                if not check_rate_limit(client_ip, scope, limit):
                    logger.warning(f"Rate limit exceeded for IP {client_ip} on scope {scope}")
                    response = JSONResponse(
                        status_code=429,
                        content={"detail": "Demasiadas peticiones. Por favor intente más tarde."},
                    )
                    response.headers[header_name] = request_id
                    return response

        response: Response = await call_next(request)
        response.headers[header_name] = request_id
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
        if norm_path in ("/auth/login", "/auth/refresh"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
        if settings.ENVIRONMENT.lower() != "development" and request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        if path != "/" and path.endswith("/") and response.status_code != 404:
            response.headers["Deprecation"] = "true"
        return response
