# app/core/settings.py
import os
from typing import Optional, List
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
    ROOT_PATH: str = ""
    # URL pública cuando la API está detrás de proxy (ej. https://apibras.finzeler.com)
    PUBLIC_URL: str = ""
    # Token Encryption
    TOKEN_EXPIRATION_MINUTES: int = 1440  # 24 horas por defecto
    TOKEN_REFRESH_EXPIRATION_MINUTES: int = 2880  # 48 horas por defecto
    SECRET_KEY: str  # Clave secreta para encriptación AES-256 (mínimo 32 caracteres recomendado)

    TIMEZONE: str = "America/Lima"

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

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
