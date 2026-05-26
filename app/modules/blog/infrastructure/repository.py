# app/modules/blog/infrastructure/repository.py
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, or_, select

from app.core.pagination.offset import PaginatedResult, PageParams
from app.modules.blog.domain.models import Blog
from app.modules.blog.interfaces.blog_repository import BlogRepositoryInterface
from app.shared.repositorie_base import BaseAsyncRepository


class SQLAlchemyBlogRepository(BaseAsyncRepository[Blog], BlogRepositoryInterface):
    def __init__(self, db: AsyncSession):
        super().__init__(Blog, db)

    async def list_filtered(
        self,
        *,
        limit: int,
        offset: int,
        search: str | None = None,
        category: str | None = None,
        enable: bool | None = None,
    ) -> PaginatedResult[Blog]:
        pagination = PageParams(skip=offset, limit=limit)
        pagination.validate_limit()

        stmt = select(Blog).where(Blog.deleted.is_(False))

        normalized_search = search.strip() if search else ""
        if normalized_search:
            pattern = f"%{normalized_search}%"
            stmt = stmt.where(
                or_(
                    Blog.title.ilike(pattern),
                    Blog.excerpt.ilike(pattern),
                    Blog.content.ilike(pattern),
                    Blog.category.ilike(pattern),
                )
            )

        normalized_category = category.strip() if category else ""
        if normalized_category:
            stmt = stmt.where(Blog.category.ilike(normalized_category))

        if enable is not None:
            stmt = stmt.where(Blog.enable.is_(enable))

        stmt = stmt.order_by(Blog.created_at.desc())
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        result = await self.session.execute(stmt.offset(pagination.skip).limit(pagination.limit))
        items = result.scalars().all()

        return PaginatedResult(
            total=total,
            items=items,
            skip=pagination.skip,
            limit=pagination.limit,
            has_next=pagination.skip + pagination.limit < total,
            has_previous=pagination.skip > 0,
        )
