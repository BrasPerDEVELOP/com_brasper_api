from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.shared.model_base import ORMBase


class Notification(ORMBase):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_inbox", "recipient_user_id", "created_at"),)
    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    recipient_user_id: Mapped[UUID] = mapped_column(ForeignKey("user.user.id"), nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("user.user.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
