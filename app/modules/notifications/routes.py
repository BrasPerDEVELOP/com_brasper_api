from datetime import datetime, timezone
from uuid import UUID
from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.routing import LegacyAliasRouter
from app.db.base import get_db
from app.modules.auth.infrastructure.dependencies import get_current_user, require_permission, require_any_permission
from app.modules.notifications.models import Notification
from app.modules.notifications.service import validate_recipients, INTERNAL_ROLES
from app.modules.users.domain.models import User
from app.modules.audit.infrastructure.stage_mutation_audit import stage_mutation_audit

router = LegacyAliasRouter(prefix="/notifications", tags=["notifications"])


def actor_id(actor):
    if not actor.get("user_id"):
        raise HTTPException(401, "Autenticación requerida")
    return UUID(str(actor["user_id"]))


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    type: str
    title: str
    body: str
    entity_type: str | None
    entity_id: UUID | None
    read_at: datetime | None
    created_at: datetime


class NoticeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10000)
    recipient_user_ids: list[UUID] = Field(min_length=1, max_length=200)


@router.get("")
async def inbox(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                actor=Depends(get_current_user), db: AsyncSession = Depends(get_db),
                _permissions=Depends(require_permission("notifications.view"))):
    own = Notification.recipient_user_id == actor_id(actor)
    total = (await db.execute(select(func.count()).select_from(Notification).where(own))).scalar_one()
    unread = (await db.execute(select(func.count()).select_from(Notification).where(own, Notification.read_at.is_(None)))).scalar_one()
    rows = (await db.execute(select(Notification).where(own).order_by(Notification.created_at.desc(), Notification.id.desc())
                            .offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return {"items": [NotificationRead.model_validate(row) for row in rows], "total": total,
            "unread_count": unread, "page": page, "page_size": page_size}


@router.get("/staff")
async def staff(actor=Depends(get_current_user), db: AsyncSession = Depends(get_db),
                _permissions=Depends(require_any_permission("notifications.view", "notifications.create", "transactions.create", "transactions.update"))):
    actor_id(actor)
    rows = (await db.execute(select(User.id, User.names, User.lastnames, User.role).where(
        User.role.in_(INTERNAL_ROLES), User.deleted.is_(False), User.enable.is_(True)
    ).order_by(User.names, User.id))).all()
    return [{"id": row.id, "name": " ".join(filter(None, [row.names, row.lastnames])) or "Usuario interno",
             "role": row.role} for row in rows]


@router.post("/read-all", dependencies=[Depends(stage_mutation_audit("notifications.read_all", "notification"))])
async def read_all(actor=Depends(get_current_user), db: AsyncSession = Depends(get_db),
                   _permissions=Depends(require_permission("notifications.view"))):
    await db.execute(update(Notification).where(Notification.recipient_user_id == actor_id(actor),
                     Notification.read_at.is_(None)).values(read_at=datetime.now(timezone.utc)))
    await db.commit()
    return {"ok": True}


@router.post("/{notification_id}/read", dependencies=[Depends(stage_mutation_audit("notifications.read", "notification"))])
async def read_one(notification_id: UUID, actor=Depends(get_current_user), db: AsyncSession = Depends(get_db),
                   _permissions=Depends(require_permission("notifications.view"))):
    row = (await db.execute(select(Notification).where(Notification.id == notification_id,
                           Notification.recipient_user_id == actor_id(actor)))).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Notificación no encontrada")
    if row.read_at is None:
        row.read_at = datetime.now(timezone.utc)
        await db.commit()
    return {"ok": True}


@router.post("/avisos", status_code=201, dependencies=[Depends(stage_mutation_audit("notifications.create", "notification"))])
async def create_notice(cmd: NoticeCreate, actor=Depends(get_current_user), db: AsyncSession = Depends(get_db),
                        _permissions=Depends(require_permission("notifications.create"))):
    sender = actor_id(actor)
    recipients = await validate_recipients(db, cmd.recipient_user_ids)
    if not cmd.title.strip() or not cmd.body.strip():
        raise HTTPException(400, "Indica título y contenido")
    for recipient in recipients:
        db.add(Notification(recipient_user_id=recipient, actor_user_id=sender, type="aviso",
                            title=cmd.title.strip(), body=cmd.body.strip()))
    await db.commit()
    return {"created": len(recipients)}
