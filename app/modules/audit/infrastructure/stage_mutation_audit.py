# app/modules/audit/infrastructure/stage_mutation_audit.py
import uuid
from collections.abc import AsyncIterator, Callable
from fastapi import Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.middlewares.auth import get_current_user
from app.middlewares.security import resolve_client_ip
from app.modules.audit.domain.models import AuditEventModel
from app.modules.audit.infrastructure.audit_repository import AuditRepository
from app.modules.audit.infrastructure.redactor import redact_data


def stage_mutation_audit(action: str, entity: str) -> Callable:
    """
    Dependencia reusable para endpoints mutables (POST/PUT/PATCH/DELETE).
    Usa la misma AsyncSession obtenida de get_db (compartida con la transacción del caso de uso),
    extrae el contexto de actor (ContextVar), request_id, IP (resolve_client_ip) y source,
    y ejecuta self.db.add(event) + flush() sin hacer commit.
    Guarda la instancia AuditEventModel en request.state.audit_event para que el handler pueda
    adjuntar entity_id, old_values y new_values.
    """
    async def dependency(
        request: Request,
        db: AsyncSession = Depends(get_db),
    ) -> AsyncIterator[AuditEventModel]:
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

        # Si viene cabecera explícita X-Client-App o header
        client_app_header = request.headers.get("X-Client-App")
        if client_app_header in ("backoffice", "www", "ia", "system"):
            source = client_app_header

        req_id_str = getattr(request.state, "request_id", None)
        request_id = uuid.UUID(req_id_str) if req_id_str else uuid.uuid4()
        client_ip = resolve_client_ip(request)
        user_agent = request.headers.get("user-agent")

        audit_repo = AuditRepository(db)
        scope = getattr(request, "scope", {})
        route = scope.get("route") if isinstance(scope, dict) else None
        declared_status_code = getattr(route, "status_code", None)
        route_status_code = declared_status_code if isinstance(declared_status_code, int) else 200
        event = await audit_repo.log_audit_event(
            action=action,
            entity=entity,
            request_id=request_id,
            actor_user_id=actor_id,
            actor_username=actor_username,
            actor_role=actor_role,
            source=source,
            ip_address=client_ip,
            user_agent=user_agent,
            method=request.method.upper(),
            path=request.url.path,
            status_code=route_status_code,
            success=True,
        )
        request.state.audit_event = event

        try:
            yield event
        except BaseException:
            # get_db revierte la transacción cuando el handler falla. Los fallos
            # HTTP se registran por FailedMutationAuditMiddleware.
            raise
        else:
            # Los casos de uso existentes confirman su transacción internamente.
            # Este segundo commit persiste el entity_id y los snapshots que el
            # handler adjunta después de ejecutar el caso de uso. La fila base ya
            # se confirmó junto con la mutación, por lo que la auditoría no puede
            # omitirse silenciosamente.
            event.old_values = redact_data(event.old_values)
            event.new_values = redact_data(event.new_values)
            event.meta_data = redact_data(event.meta_data)
            await db.flush()
            await db.commit()

    dependency.__audit_dependency__ = True
    dependency.__audit_action__ = action
    dependency.__audit_entity__ = entity
    return dependency
