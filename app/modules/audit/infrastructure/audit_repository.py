# app/modules/audit/infrastructure/audit_repository.py
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.domain.models import AuditEventModel, LoginEventModel
from app.modules.audit.infrastructure.redactor import redact_data


def _utc_now() -> datetime:
    """Retorna datetime actual con timezone UTC (aware)."""
    return datetime.now(timezone.utc)


class AuditRepository:
    """
    Repositorio de auditoría de solo adición (append-only).
    Sin métodos de modificación ni eliminación. Nunca ejecuta commit por su cuenta.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_audit_event(
        self,
        action: str,
        entity: str,
        request_id: uuid.UUID,
        actor_user_id: Optional[uuid.UUID] = None,
        actor_username: Optional[str] = None,
        actor_role: Optional[str] = None,
        entity_id: Optional[str] = None,
        description: Optional[str] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        source: str = "backoffice",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        method: Optional[str] = None,
        path: Optional[str] = None,
        status_code: Optional[int] = None,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEventModel:
        now = _utc_now()
        event = AuditEventModel(
            id=uuid.uuid4(),
            actor_user_id=actor_user_id,
            actor_username=actor_username,
            actor_role=actor_role,
            action=action,
            entity=entity,
            entity_id=str(entity_id) if entity_id is not None else None,
            description=description,
            old_values=redact_data(old_values) if old_values is not None else None,
            new_values=redact_data(new_values) if new_values is not None else None,
            source=source,
            ip_address=ip_address,
            user_agent=user_agent,
            method=method,
            path=path,
            status_code=status_code,
            request_id=request_id,
            success=success,
            meta_data=redact_data(metadata) if metadata is not None else None,
            created_at=now,
        )
        self.db.add(event)
        await self.db.flush()
        return event

    async def log_login_event(
        self,
        success: bool,
        request_id: uuid.UUID,
        attempted_username: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
        failure_reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        browser: Optional[str] = None,
        os: Optional[str] = None,
        device: Optional[str] = None,
        source: str = "backoffice",
        session_id: Optional[uuid.UUID] = None,
    ) -> LoginEventModel:
        now = _utc_now()
        event = LoginEventModel(
            id=uuid.uuid4(),
            user_id=user_id,
            attempted_username=attempted_username,
            success=success,
            failure_reason=failure_reason,
            ip_address=ip_address,
            user_agent=user_agent,
            browser=browser,
            os=os,
            device=device,
            source=source,
            request_id=request_id,
            session_id=session_id,
            created_at=now,
        )
        self.db.add(event)
        await self.db.flush()
        return event
