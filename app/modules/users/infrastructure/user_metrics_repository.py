"""Agregados del directorio; no devuelve teléfonos ni identificaciones."""
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.domain.models import User


class UserMetricsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def grouped(self, role: str | None = None):
        country = func.lower(func.trim(func.coalesce(User.country, "")))
        phone_code = func.trim(func.coalesce(User.code_phone, ""))
        area = func.trim(func.coalesce(User.local_area_code, ""))
        name = func.trim(func.coalesce(User.local_area_name, ""))
        stmt = select(
            country.label("country"), phone_code.label("phone_code"),
            area.label("area"), name.label("name"),
            func.count().label("total"),
            func.sum(case((User.enable.is_(True), 1), else_=0)).label("enabled"),
        ).where(User.deleted.is_(False))
        if role:
            stmt = stmt.where(func.lower(User.role) == role.strip().lower())
        result = await self.session.execute(stmt.group_by(country, phone_code, area, name))
        return result.mappings().all()
