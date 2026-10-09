"""Short-lived channel grants issued only from the customer's authenticated account."""
from datetime import datetime
from uuid import UUID
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from app.shared.model_base import ORMBaseModel


class AIIdentityLink(ORMBaseModel):
    __tablename__ = "ai_identity_links"
    __table_args__ = {"schema": "user"}
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("user.user.id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    subject_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    grant_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    grant_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
