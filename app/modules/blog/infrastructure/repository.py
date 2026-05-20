# app/modules/blog/infrastructure/repository.py
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.blog.domain.models import Blog
from app.modules.blog.interfaces.blog_repository import BlogRepositoryInterface
from app.shared.repositorie_base import BaseAsyncRepository


class SQLAlchemyBlogRepository(BaseAsyncRepository[Blog], BlogRepositoryInterface):
    def __init__(self, db: AsyncSession):
        super().__init__(Blog, db)
