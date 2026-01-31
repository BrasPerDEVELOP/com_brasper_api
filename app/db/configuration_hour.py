from sqlalchemy.orm import mapped_column
from sqlalchemy import DateTime, text
from datetime import datetime

from app.core.settings import get_settings


def create_timestamp_columns():
    tz = get_settings().TIMEZONE
    return (
        mapped_column(
            DateTime(timezone=True),
            server_default=text(f"(now() AT TIME ZONE '{tz}')"),
            nullable=False,
        ),
        mapped_column(
            DateTime(timezone=True),
            server_default=text(f"(now() AT TIME ZONE '{tz}')"),
            onupdate=text("now()"),
            nullable=False,
        ),
    )
