from typing import Optional

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.model_base import ORMBaseModel


class HomeBanner(ORMBaseModel):
    __tablename__ = "home_banner"
    __table_args__ = {"schema": "home_banner"}

    banner_es: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    banner_pr: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    banner_en: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    indicators: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    appearance: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    show_image: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    show_indicators: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)



class HomePopup(ORMBaseModel):
    __tablename__ = "home_popup"
    __table_args__ = {"schema": "home_popup"}

    popup_es: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    popup_pr: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    popup_en: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
