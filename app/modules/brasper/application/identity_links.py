import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy import func, or_, select, update
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Literal
from app.modules.brasper.domain.identity_link import AIIdentityLink
from app.modules.users.domain.models import User
from .ai_service import BrasperAIService


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class ChannelSubject(BaseModel):
    model_config = ConfigDict(extra="forbid")
    channel: Literal["telegram", "webchat", "whatsapp"]
    subject: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9:+._-]+$")

    @model_validator(mode="after")
    def valid(self):
        if self.channel == "telegram" and not re.fullmatch(r"tg:[1-9][0-9]{0,19}", self.subject):
            raise ValueError("Usa la referencia del chat privado de Telegram")
        if self.channel == "whatsapp" and not self.subject.startswith("wa:"):
            raise ValueError("Referencia de canal inválida")
        return self


class RedeemLink(ChannelSubject):
    link_token: str = Field(min_length=43, max_length=43, pattern=r"^[A-Za-z0-9_-]{43}$")


class Unavailable(ValueError):
    pass


class TooMany(ValueError):
    pass


class IdentityLinks:
    def __init__(self, session):
        self.session = session

    async def _user(self, user_id):
        return (await self.session.scalars(BrasperAIService(self.session)._active_clients().where(User.id == user_id))).first()

    async def issue(self, user_id: UUID, target: ChannelSubject):
        now = datetime.now(timezone.utc)
        await self.session.execute(select(User.id).where(User.id == user_id).with_for_update())
        if await self._user(user_id) is None:
            raise Unavailable("Identidad no disponible")
        count = await self.session.scalar(select(func.count(AIIdentityLink.id)).where(
            AIIdentityLink.user_id == user_id, AIIdentityLink.expires_at > now,
            AIIdentityLink.consumed_at.is_(None), AIIdentityLink.deleted.is_(False)))
        if count >= 3:
            raise TooMany("Ya hay vínculos pendientes; espera a que venzan")
        token = secrets.token_urlsafe(32)
        expiry = now + timedelta(minutes=5)
        self.session.add(AIIdentityLink(user_id=user_id, channel=target.channel,
            subject_hash=digest(target.subject), token_hash=digest(token), expires_at=expiry))
        await self.session.commit()
        return {"link_token": token, "expires_at": expiry, "channel": target.channel}

    async def redeem(self, target: RedeemLink):
        now = datetime.now(timezone.utc)
        row = (await self.session.scalars(select(AIIdentityLink).where(
            AIIdentityLink.token_hash == digest(target.link_token), AIIdentityLink.channel == target.channel,
            AIIdentityLink.subject_hash == digest(target.subject), AIIdentityLink.expires_at > now,
            AIIdentityLink.consumed_at.is_(None), AIIdentityLink.deleted.is_(False), AIIdentityLink.enable.is_(True)))).first()
        if row is None or await self._user(row.user_id) is None:
            raise Unavailable("Vínculo inválido, vencido o ya utilizado")
        grant = secrets.token_urlsafe(32)
        expiry = now + timedelta(minutes=30)
        claimed = await self.session.execute(update(AIIdentityLink).where(
            AIIdentityLink.id == row.id, AIIdentityLink.consumed_at.is_(None),
            AIIdentityLink.expires_at > now).values(consumed_at=now, grant_hash=digest(grant), grant_expires_at=expiry)
            .returning(AIIdentityLink.user_id))
        user_id = claimed.scalar_one_or_none()
        if user_id is None:
            raise Unavailable("Vínculo inválido, vencido o ya utilizado")
        await self.session.commit()
        return {"user_id": str(user_id), "grant": grant, "expires_at": expiry}

    async def authorize(self, user_id, grant, channel, subject):
        if not grant or not channel or not subject:
            raise Unavailable("Identidad no autorizada")
        now = datetime.now(timezone.utc)
        row = (await self.session.scalars(select(AIIdentityLink).where(
            AIIdentityLink.user_id == user_id, AIIdentityLink.grant_hash == digest(grant),
            AIIdentityLink.channel == channel, AIIdentityLink.subject_hash == digest(subject),
            AIIdentityLink.consumed_at.is_not(None), AIIdentityLink.grant_expires_at > now,
            AIIdentityLink.deleted.is_(False), AIIdentityLink.enable.is_(True)))).first()
        if row is None or await self._user(user_id) is None:
            raise Unavailable("Identidad no autorizada")

    async def revoke_all(self, user_id: UUID):
        """El cliente retira desde su cuenta los códigos pendientes y grants vigentes."""
        now = datetime.now(timezone.utc)
        result = await self.session.execute(update(AIIdentityLink).where(
            AIIdentityLink.user_id == user_id, AIIdentityLink.deleted.is_(False),
            or_(AIIdentityLink.consumed_at.is_(None), AIIdentityLink.grant_expires_at > now)).values(deleted=True))
        await self.session.commit()
        return {"revoked": result.rowcount or 0}
