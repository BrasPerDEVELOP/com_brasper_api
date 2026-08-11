# app/core/settings.py
from typing import Optional
import hashlib
import hmac
import ipaddress
import time
from urllib.parse import quote, urlparse
from pydantic import model_validator
from pydantic_settings import BaseSettings
from aiocache import caches

# Sufijos públicos de dos etiquetas relevantes para los dominios de Brasper. La
# lista completa (PSL) no justifica una dependencia extra aquí: si un sufijo no
# está, el cálculo agrupa de más y la validación de cookies deja pasar la
# configuración en vez de rechazar un despliegue válido.
_MULTI_LABEL_PUBLIC_SUFFIXES = frozenset({"com.pe", "com.br", "com.mx", "com.ar", "co.uk"})


def _registrable_domain(host: Optional[str]) -> Optional[str]:
    """Dominio registrable (eTLD+1) de un host, que es la unidad de `SameSite`."""
    if not host:
        return None
    labels = host.lower().strip(".").split(".")
    if len(labels) < 2:
        return host.lower()
    if len(labels) > 2 and ".".join(labels[-2:]) in _MULTI_LABEL_PUBLIC_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


class Settings(BaseSettings):
    # PostgreSQL
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int

    # FastAPI / app
    DEBUG: bool
    LOG_LEVEL: str
    ENVIRONMENT: str = "development"
    # Si es False, la API no exige token (útil mientras el front no envía Bearer).
    AUTH_REQUIRED: bool = False
    ROOT_PATH: str = ""
    # URL pública cuando la API está detrás de proxy (ej. https://apibras.finzeler.com)
    PUBLIC_URL: str = ""
    # URL del frontend para redirigir tras login OAuth (opcional)
    FRONTEND_URL: Optional[str] = None
    # Token Encryption
    TOKEN_EXPIRATION_MINUTES: int = 1440  # 24 horas por defecto
    TOKEN_REFRESH_EXPIRATION_MINUTES: int = 2880  # 48 horas por defecto
    SECRET_KEY: str  # Clave secreta para encriptación AES-256 (mínimo 32 caracteres recomendado)
    # Secreto compartido exclusivamente con com_brasper_ia. Si está vacío,
    # los endpoints /brasper/ai responden 503 y nunca quedan abiertos.
    BRASPER_IA_SHARED_SECRET: str = ""

    # Seguridad y Middleware (Fase 1)
    CORS_ALLOWED_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]
    TRUSTED_PROXY_CIDRS: list[str] = ["127.0.0.1/32", "::1/128"]
    REQUEST_ID_HEADER: str = "X-Request-ID"

    # Limits por IP (requests / minuto)
    RATE_LIMIT_LOGIN: int = 10
    RATE_LIMIT_REGISTER: int = 5
    RATE_LIMIT_PASSWORD_RESET: int = 5
    RATE_LIMIT_CONTACT_FORM: int = 5

    # JWT y Sesiones (Fase 2)
    AUTH_MODE: str = "dual"  # legacy | dual | jwt
    JWT_SECRET_KEY: str = "dev-jwt-secret-key-change-in-production-32-chars-minimum"
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "com.brasper.api"
    JWT_AUDIENCE: str = "com.brasper.app"
    JWT_ACCESS_TTL_MINUTES: int = 15
    REFRESH_TOKEN_TTL_DAYS: int = 7
    REFRESH_COOKIE_NAME: str = "brasper_refresh_token"
    REFRESH_COOKIE_SECURE: bool = False
    REFRESH_COOKIE_SAMESITE: str = "lax"
    REFRESH_COOKIE_DOMAIN: Optional[str] = None

    TIMEZONE: str = "America/Lima"
    # Variables del módulo world_cup (retirado el 2026-07-22). Se conservan
    # declaradas para tolerar .env desplegados que aún las definen.
    FOOTBALL_DATA_API_TOKEN: str = ""
    FOOTBALL_DATA_COMPETITION_CODE: str = "WC"
    SPORTMONKS_API_TOKEN: str = ""
    SPORTMONKS_WORLD_CUP_LEAGUE_ID: str = ""
    WORLD_CUP_SCHEDULER_ENABLED: bool = True
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_USE_TLS: bool = True

    # Cloudflare R2 (S3-compatible) — almacenamiento obligatorio de archivos
    R2_ENDPOINT_URL: str
    R2_ACCESS_KEY_ID: str
    R2_SECRET_ACCESS_KEY: str
    R2_BUCKET_NAME: str
    # URL pública del bucket (dominio custom o r2.dev). Si está vacía, /media/ hace proxy desde R2.
    R2_PUBLIC_URL: str = ""
    # Secreto compartido con el Worker para firmar las URL de comprobantes. Sin
    # él, los comprobantes siguen sirviéndose por /media/ con proxy autenticado:
    # el fallback nunca los expone, solo renuncia al CDN.
    MEDIA_SIGNING_SECRET: str = ""
    MEDIA_SIGNED_URL_TTL_SECONDS: int = 1800

    @model_validator(mode="after")
    def validate_r2_config(self) -> "Settings":
        missing = [
            name
            for name, value in (
                ("R2_ENDPOINT_URL", self.R2_ENDPOINT_URL),
                ("R2_ACCESS_KEY_ID", self.R2_ACCESS_KEY_ID),
                ("R2_SECRET_ACCESS_KEY", self.R2_SECRET_ACCESS_KEY),
                ("R2_BUCKET_NAME", self.R2_BUCKET_NAME),
            )
            if not value
        ]
        if missing:
            raise ValueError(
                "Cloudflare R2 es obligatorio. Configura en .env: "
                + ", ".join(missing)
            )
        if self.AUTH_MODE.lower() not in ("legacy", "dual", "jwt"):
            raise ValueError("AUTH_MODE debe ser uno de: legacy, dual, jwt")
        if self.JWT_ALGORITHM != "HS256":
            raise ValueError("JWT_ALGORITHM debe ser exactamente HS256")
        if self.REFRESH_COOKIE_SAMESITE.lower() not in ("lax", "strict", "none"):
            raise ValueError("REFRESH_COOKIE_SAMESITE debe ser lax, strict o none")
        if self.REFRESH_COOKIE_SAMESITE.lower() == "none" and not self.REFRESH_COOKIE_SECURE:
            raise ValueError("REFRESH_COOKIE_SECURE=True es obligatorio cuando SameSite=None")
        if not 1 <= self.JWT_ACCESS_TTL_MINUTES <= 60:
            raise ValueError("JWT_ACCESS_TTL_MINUTES debe estar entre 1 y 60")
        if not 1 <= self.REFRESH_TOKEN_TTL_DAYS <= 30:
            raise ValueError("REFRESH_TOKEN_TTL_DAYS debe estar entre 1 y 30")
        if any(origin == "*" for origin in self.CORS_ALLOWED_ORIGINS):
            raise ValueError("CORS_ALLOWED_ORIGINS no puede contener '*' con credenciales")
        for cidr in self.TRUSTED_PROXY_CIDRS:
            try:
                ipaddress.ip_network(cidr, strict=False)
            except ValueError as exc:
                raise ValueError(f"TRUSTED_PROXY_CIDRS contiene un CIDR inválido: {cidr}") from exc
        if self.ENVIRONMENT.lower() != "development":
            if not self.JWT_SECRET_KEY or self.JWT_SECRET_KEY.startswith("dev-") or len(self.JWT_SECRET_KEY) < 32:
                raise ValueError("JWT_SECRET_KEY separado y seguro (mínimo 32 caracteres) es obligatorio fuera de desarrollo")
            if not self.REFRESH_COOKIE_SECURE:
                raise ValueError("REFRESH_COOKIE_SECURE=True es obligatorio fuera de desarrollo")
            if not self.AUTH_REQUIRED:
                raise ValueError("AUTH_REQUIRED=True es obligatorio fuera de desarrollo")
            if self.JWT_SECRET_KEY == self.SECRET_KEY:
                raise ValueError("JWT_SECRET_KEY debe ser diferente de SECRET_KEY")
            if self.PUBLIC_URL and urlparse(self.PUBLIC_URL).scheme != "https":
                raise ValueError("PUBLIC_URL debe usar HTTPS fuera de desarrollo")
            for origin in self.CORS_ALLOWED_ORIGINS:
                parsed = urlparse(origin)
                if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
                    raise ValueError(f"Origen CORS remoto sin HTTPS: {origin}")
            self._validate_refresh_cookie_reaches_frontends()
        return self

    def _validate_refresh_cookie_reaches_frontends(self) -> None:
        """
        Falla al arrancar si la cookie de refresh no llegaría a algún frontend.

        `SameSite=Lax` solo acompaña navegaciones de primer nivel, no peticiones
        XHR. Como `POST /auth/refresh` se hace por XHR, un frontend en otro
        dominio registrable que el de la API nunca enviaría la cookie: todos los
        usuarios quedarían en un bucle de 401 sin poder mantener la sesión.
        """
        if self.REFRESH_COOKIE_SAMESITE.lower() == "none":
            return
        api_domain = _registrable_domain(urlparse(self.PUBLIC_URL).hostname) if self.PUBLIC_URL else None
        if not api_domain:
            return
        for origin in self.CORS_ALLOWED_ORIGINS:
            host = urlparse(origin).hostname
            if not host or host in {"localhost", "127.0.0.1"}:
                continue
            origin_domain = _registrable_domain(host)
            if origin_domain != api_domain:
                raise ValueError(
                    f"El origen {origin} es cross-site respecto a la API ({api_domain}), "
                    "así que la cookie de refresh no viajaría en el XHR de /auth/refresh. "
                    "Configura REFRESH_COOKIE_SAMESITE=none con REFRESH_COOKIE_SECURE=True, "
                    "o sirve la API y el frontend bajo el mismo dominio registrable."
                )

    def sign_media_key(self, key: str, expires_at: int) -> str:
        """Firma HMAC-SHA256 de `key` hasta `expires_at`, verificada por el Worker."""
        message = f"{key}\n{expires_at}".encode()
        return hmac.new(
            self.MEDIA_SIGNING_SECRET.encode(), message, hashlib.sha256
        ).hexdigest()

    def signed_media_url(self, key: str, now: Optional[int] = None) -> str:
        """URL del Worker con caducidad corta para un archivo privado."""
        expires_at = (int(time.time()) if now is None else now) + self.MEDIA_SIGNED_URL_TTL_SECONDS
        signature = self.sign_media_key(key, expires_at)
        return f"{self.R2_PUBLIC_URL.rstrip('/')}/{key}?exp={expires_at}&sig={signature}"

    def media_public_url(self, relative_path: str) -> str:
        """
        URL pública de un archivo (Worker/R2 directo o /media/ vía API).

        Los comprobantes nunca salen con una URL desnuda del Worker: o van
        firmados y con caducidad, o se sirven por `/media/`, donde la API
        comprueba que quien pide es el dueño de la transacción o tiene
        `transactions.view`.
        """
        path = relative_path.lstrip("/")
        api_fallback = (
            f"{self.PUBLIC_URL.rstrip('/')}/media/{path}" if self.PUBLIC_URL else f"/media/{path}"
        )
        if path.startswith("transaction_vouchers/"):
            if self.R2_PUBLIC_URL and self.MEDIA_SIGNING_SECRET:
                return self.signed_media_url(path)
            return api_fallback
        if self.R2_PUBLIC_URL:
            return f"{self.R2_PUBLIC_URL.rstrip('/')}/{path}"
        return api_fallback

    @property
    def database_url(self) -> str:
        # URL-encode password to handle special chars like @, #, etc.
        password = quote(self.POSTGRES_PASSWORD, safe="")
        return f"postgresql://{self.POSTGRES_USER}:{password}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    def configure_cache(self):
        """Configura cache (sin Redis, usando memoria)"""
        caches.set_config({
            'default': {
                'cache': 'aiocache.SimpleMemoryCache',
                'timeout': 300,
            }
        })

    class Config:
        env_file = ".env"
        case_sensitive = True
        # El .env es compartido con docker-compose (API_PORT, etc.). Sin esto,
        # pydantic-settings usa extra="forbid" y cualquier clave ajena a la app
        # hace fallar el arranque.
        extra = "ignore"


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
