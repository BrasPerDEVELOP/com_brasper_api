"""Helpers para exponer rutas de media como URL pública completa (Cloudflare R2/Worker).

La base de datos guarda la key relativa (ej. "home_banner/banner_es_xxx.webp").
En las respuestas de la API se devuelve la URL completa vía settings.media_public_url,
sin tocar el valor almacenado (portable: si cambia el dominio del CDN, no hay migración).
"""
from typing import List, Optional

from app.core.settings import get_settings


def to_media_url(value: Optional[str]) -> Optional[str]:
    """Convierte una key relativa en URL pública completa.

    - None / "" → se devuelve tal cual.
    - Ya es http(s):// → se devuelve sin cambios (idempotente).
    - key relativa → settings.media_public_url(key).
    """
    if not value:
        return value
    if value.startswith(("http://", "https://")):
        return value
    return get_settings().media_public_url(value)


def to_media_urls(values: Optional[List[str]]) -> Optional[List[str]]:
    """Aplica to_media_url a una lista de keys."""
    if not values:
        return values
    return [to_media_url(v) for v in values]
