# app/modules/blog/domain/models.py
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.model_base import ORMBaseModel


class Blog(ORMBaseModel):
    __tablename__ = "blog"
    __table_args__ = {"schema": "blog"}

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    excerpt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    public_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True, index=True)
    read_time: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    language: Mapped[str] = mapped_column(String(10), nullable=False)
