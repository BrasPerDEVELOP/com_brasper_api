# app/core/routing.py
from typing import Any, Callable

from fastapi import APIRouter

class LegacyAliasRouter(APIRouter):
    """
    Router personalizado que para cada ruta sin barra final (salvo '/')
    registra de forma oculta (include_in_schema=False) la variante legacy con barra final
    que ejecuta exactamente la misma función/handler sin redirección (307/308).
    Preserva todos los kwargs de FastAPI 0.115+ sin provocar sorpresas.
    """

    def add_api_route(
        self,
        path: str,
        endpoint: Callable[..., Any],
        **kwargs: Any,
    ) -> None:
        # Normalizar path canónico
        canonical_path = path
        if canonical_path != "" and canonical_path != "/" and canonical_path.endswith("/"):
            canonical_path = canonical_path.rstrip("/")

        # Llamar a la implementación base con kwargs
        super().add_api_route(canonical_path, endpoint, **kwargs)

        # Un handler declarado con path="" vive en el prefijo del router. Su
        # alias legacy es "/" relativo al prefijo (p. ej. /blog/).
        include_in_schema = kwargs.get("include_in_schema", True)
        if canonical_path != "/" and include_in_schema:
            alias_path = "/" if canonical_path == "" else f"{canonical_path}/"
            alias_kwargs = kwargs.copy()
            alias_kwargs["include_in_schema"] = False

            name = kwargs.get("name") or (endpoint.__name__ if hasattr(endpoint, "__name__") else None)
            if name:
                alias_kwargs["name"] = f"{name}_legacy_alias"

            operation_id = kwargs.get("operation_id")
            if operation_id:
                alias_kwargs["operation_id"] = f"{operation_id}_legacy_alias"

            super().add_api_route(alias_path, endpoint, **alias_kwargs)
