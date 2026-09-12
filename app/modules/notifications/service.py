from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select
from app.modules.users.domain.models import User
from app.modules.notifications.models import Notification

INTERNAL_ROLES = ("admin", "sales", "accounting", "marketing", "user")


async def validate_recipients(db, ids):
    unique = list(dict.fromkeys(ids))
    if not unique:
        return []
    rows = (await db.execute(select(User.id).where(
        User.id.in_(unique), User.role.in_(INTERNAL_ROLES),
        User.deleted.is_(False), User.enable.is_(True),
    ))).scalars().all()
    if set(rows) != set(unique):
        raise HTTPException(400, "Solo se pueden mencionar usuarios internos activos")
    return unique


async def add_mentions(db, ids, transaction_id, body):
    recipients = await validate_recipients(db, ids)
    if not recipients:
        return
    from app.middlewares.auth import get_current_user
    actor = get_current_user() or {}
    actor_id = UUID(str(actor['user_id'])) if actor.get('user_id') else None
    for recipient in recipients:
        db.add(Notification(recipient_user_id=recipient, actor_user_id=actor_id,
                            type="mention", title="Te mencionaron en una transacción",
                            body=body or "", entity_type="transaction", entity_id=transaction_id))
