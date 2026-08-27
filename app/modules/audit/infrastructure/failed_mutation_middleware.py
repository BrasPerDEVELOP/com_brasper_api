# app/modules/audit/infrastructure/failed_mutation_middleware.py
import uuid
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.db.base import AsyncSessionLocal
from app.middlewares.auth import get_current_user
from app.middlewares.security import resolve_client_ip
from app.modules.audit.infrastructure.audit_repository import AuditRepository

logger = logging.getLogger(__name__)

EXCLUDED_MUTATION_PATHS = {"/auth/login", "/auth/refresh"}


class FailedMutationAuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware que captura fallos en peticiones mutables (POST, PUT, PATCH, DELETE)
    y respuestas HTTP 401/403 en superficies sensibles.
    Escribe el evento 'mutation.failed' o 'security.unauthorized' en una sesión de BD aislada
    después de emitir la respuesta, sin guardar cuerpos ni secretos.
    """
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        method = request.method.upper()
        path = request.url.path
        norm_path = path.rstrip("/") or "/"
        status_code = response.status_code

        # Excluir rutas de login/refresh para no duplicar login_event
        if norm_path in EXCLUDED_MUTATION_PATHS:
            return response

        is_mutation_failure = method in ("POST", "PUT", "PATCH", "DELETE") and status_code >= 400
        is_security_failure = status_code in (401, 403) and norm_path != "/health" and norm_path != "/"

        if is_mutation_failure or is_security_failure:
            try:
                actor = get_current_user()
                actor_id = None
                actor_username = None
                actor_role = None
                source = "backoffice"

                if actor:
                    if actor.get("user_id"):
                        try:
                            actor_id = uuid.UUID(str(actor["user_id"]))
                        except (ValueError, TypeError):
                            actor_id = None
                    actor_username = actor.get("username")
                    actor_role = actor.get("role")
                    if actor.get("client_app") in ("backoffice", "www", "ia", "system"):
                        source = actor["client_app"]
                # No atribuir identidad desde el JWT crudo: para una respuesta
                # 401 el token puede estar vencido, alterado o directamente ser
                # falso. Solo el contexto poblado por TokenAuthMiddleware contiene
                # una identidad que ya pasó la validación de autenticación.

                client_app_header = request.headers.get("X-Client-App")
                if client_app_header in ("backoffice", "www", "ia", "system"):
                    source = client_app_header

                req_id_str = getattr(request.state, "request_id", None)
                request_id = uuid.UUID(req_id_str) if req_id_str else uuid.uuid4()
                client_ip = resolve_client_ip(request)
                user_agent = request.headers.get("user-agent")

                action = "security.unauthorized" if status_code in (401, 403) else "mutation.failed"
                entity = norm_path.split("/")[1] if len(norm_path.split("/")) > 1 else "api"

                async with AsyncSessionLocal() as audit_db:
                    if actor_id and not actor_username:
                        from app.modules.users.domain.models import User
                        user_row = await audit_db.get(User, actor_id)
                        if user_row:
                            actor_username = user_row.email or user_row.username
                            actor_role = getattr(user_row, "role", None) or actor_role

                    repo = AuditRepository(audit_db)
                    await repo.log_audit_event(
                        action=action,
                        entity=entity,
                        request_id=request_id,
                        actor_user_id=actor_id,
                        actor_username=actor_username,
                        actor_role=actor_role,
                        description=f"HTTP {status_code} failure on {method} {path}",
                        source=source,
                        ip_address=client_ip,
                        user_agent=user_agent,
                        method=method,
                        path=path,
                        status_code=status_code,
                        success=False,
                    )
                    await audit_db.commit()
            except Exception as err:
                logger.error(f"Error registrando auditoría de fallo de mutación: {err}")

        return response
