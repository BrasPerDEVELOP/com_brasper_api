# app/core/settings.py
from typing import Optional
from urllib.parse import quote
from pydantic import model_validator
from pydantic_settings import BaseSettings
from aiocache import caches


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
        return self

    def media_public_url(self, relative_path: str) -> str:
        """URL pública de un archivo (R2 directo o /media/ vía API)."""
        path = relative_path.lstrip("/")
        if self.R2_PUBLIC_URL:
            return f"{self.R2_PUBLIC_URL.rstrip('/')}/{path}"
        base = self.PUBLIC_URL.rstrip("/") if self.PUBLIC_URL else ""
        return f"{base}/media/{path}" if base else f"/media/{path}"

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


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
