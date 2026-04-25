from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.model_base import ORMBaseModel


class ContacForm(ORMBaseModel):
    __tablename__ = "contac_form"
    __table_args__ = {"schema": "brasper"}

    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    affiliation: Mapped[str] = mapped_column(String(500), nullable=False)
    profile: Mapped[str] = mapped_column(String(200), nullable=False)
    interest: Mapped[str] = mapped_column(String(500), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    locale: Mapped[str] = mapped_column(String(10), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
