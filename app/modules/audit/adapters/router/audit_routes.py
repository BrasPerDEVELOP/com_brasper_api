from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from typing import Annotated, Literal, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.routing import LegacyAliasRouter
from app.db.base import get_db
from app.modules.audit.domain.models import AuditEventModel, LoginEventModel
from app.modules.auth.infrastructure.dependencies import require_permission


router = LegacyAliasRouter(prefix="/audit", tags=["audit"])


def _ip_to_str(value: object) -> object:
    """
    Las columnas `ip_address` son INET, así que el driver devuelve objetos
    `IPv4Address`/`IPv6Address` y no cadenas. Sin esta coerción, serializar la
    fila falla con 422 y la bitácora entera queda inaccesible.
    """
    if isinstance(value, (IPv4Address, IPv6Address)):
        return str(value)
    return value


IpAddressStr = Annotated[Optional[str], BeforeValidator(_ip_to_str)]


class AuditEventDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    actor_user_id: Optional[UUID] = None
    actor_username: Optional[str] = None
    actor_role: Optional[str] = None
    action: str
    entity: str
    entity_id: Optional[str] = None
    description: Optional[str] = None
    old_values: Optional[dict] = None
    new_values: Optional[dict] = None
    source: str
    ip_address: IpAddressStr = None
    user_agent: Optional[str] = None
    method: Optional[str] = None
    path: Optional[str] = None
    status_code: Optional[int] = None
    request_id: UUID
    success: bool
    metadata: Optional[dict] = Field(default=None, validation_alias="meta_data")
    created_at: datetime


class AuditEventSummaryDTO(BaseModel):
    """Fila liviana: los snapshots y user-agent solo salen en el detalle."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_user_id: Optional[UUID] = None
    actor_username: Optional[str] = None
    actor_role: Optional[str] = None
    action: str
    entity: str
    entity_id: Optional[str] = None
    description: Optional[str] = None
    source: str
    ip_address: IpAddressStr = None
    method: Optional[str] = None
    path: Optional[str] = None
    status_code: Optional[int] = None
    request_id: UUID
    success: bool
    created_at: datetime


class LoginEventDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: Optional[UUID] = None
    attempted_username: Optional[str] = None
    success: bool
    failure_reason: Optional[str] = None
    ip_address: IpAddressStr = None
    user_agent: Optional[str] = None
    browser: Optional[str] = None
    os: Optional[str] = None
    device: Optional[str] = None
    source: str
    request_id: UUID
    session_id: Optional[UUID] = None
    created_at: datetime


class AuditEventPage(BaseModel):
    total: int
    items: list[AuditEventSummaryDTO]
    skip: int
    limit: int


class LoginEventPage(BaseModel):
    total: int
    items: list[LoginEventDTO]
    skip: int
    limit: int


def _date_filters(model, created_from: Optional[datetime], created_to: Optional[datetime]):
    filters = []
    if created_from is not None:
        filters.append(model.created_at >= created_from)
    if created_to is not None:
        filters.append(model.created_at <= created_to)
    return filters


@router.get("/events", response_model=AuditEventPage)
async def list_audit_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    actor_user_id: Optional[UUID] = None,
    action: Optional[str] = None,
    entity: Optional[str] = None,
    entity_id: Optional[str] = None,
    source: Optional[Literal["backoffice", "www", "ia", "system"]] = None,
    ip_address: Optional[str] = Query(None, min_length=2, max_length=45),
    success: Optional[bool] = None,
    request_id: Optional[UUID] = None,
    search: Optional[str] = Query(None, max_length=200),
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    _permissions=Depends(require_permission("audit.view")),
    db: AsyncSession = Depends(get_db),
):
    filters = _date_filters(AuditEventModel, created_from, created_to)
    if actor_user_id is not None:
        filters.append(AuditEventModel.actor_user_id == actor_user_id)
    if action:
        filters.append(AuditEventModel.action == action.strip())
    if entity:
        filters.append(AuditEventModel.entity == entity.strip())
    if entity_id:
        filters.append(AuditEventModel.entity_id == entity_id.strip())
    if source:
        filters.append(AuditEventModel.source == source)
    if ip_address:
        filters.append(cast(AuditEventModel.ip_address, String) == ip_address.strip())
    if success is not None:
        filters.append(AuditEventModel.success.is_(success))
    if request_id is not None:
        filters.append(AuditEventModel.request_id == request_id)
    if search and search.strip():
        needle = f"%{search.strip()}%"
        filters.append(
            or_(
                AuditEventModel.actor_username.ilike(needle),
                AuditEventModel.description.ilike(needle),
                AuditEventModel.entity_id.ilike(needle),
                cast(AuditEventModel.request_id, String).ilike(needle),
            )
        )

    total = await db.scalar(select(func.count()).select_from(AuditEventModel).where(*filters))
    result = await db.execute(
        select(AuditEventModel)
        .where(*filters)
        .order_by(AuditEventModel.created_at.desc(), AuditEventModel.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return AuditEventPage(
        total=int(total or 0),
        items=[AuditEventSummaryDTO.model_validate(item) for item in result.scalars().all()],
        skip=skip,
        limit=limit,
    )


@router.get("/events/{event_id}", response_model=AuditEventDTO)
async def get_audit_event(
    event_id: UUID,
    _permissions=Depends(require_permission("audit.view")),
    db: AsyncSession = Depends(get_db),
):
    event = await db.get(AuditEventModel, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evento no encontrado")
    return AuditEventDTO.model_validate(event)


@router.get("/logins", response_model=LoginEventPage)
async def list_login_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user_id: Optional[UUID] = None,
    success: Optional[bool] = None,
    source: Optional[Literal["backoffice", "www", "ia", "system"]] = None,
    ip_address: Optional[str] = Query(None, min_length=2, max_length=45),
    attempted_username: Optional[str] = Query(None, max_length=255),
    request_id: Optional[UUID] = None,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    _permissions=Depends(require_permission("audit.view")),
    db: AsyncSession = Depends(get_db),
):
    filters = _date_filters(LoginEventModel, created_from, created_to)
    if user_id is not None:
        filters.append(LoginEventModel.user_id == user_id)
    if success is not None:
        filters.append(LoginEventModel.success.is_(success))
    if source:
        filters.append(LoginEventModel.source == source)
    if ip_address:
        filters.append(cast(LoginEventModel.ip_address, String) == ip_address.strip())
    if attempted_username:
        filters.append(LoginEventModel.attempted_username.ilike(f"%{attempted_username.strip()}%"))
    if request_id is not None:
        filters.append(LoginEventModel.request_id == request_id)

    total = await db.scalar(select(func.count()).select_from(LoginEventModel).where(*filters))
    result = await db.execute(
        select(LoginEventModel)
        .where(*filters)
        .order_by(LoginEventModel.created_at.desc(), LoginEventModel.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return LoginEventPage(
        total=int(total or 0),
        items=[LoginEventDTO.model_validate(item) for item in result.scalars().all()],
        skip=skip,
        limit=limit,
    )
