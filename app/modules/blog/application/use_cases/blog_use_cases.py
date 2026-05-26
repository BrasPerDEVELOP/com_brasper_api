# app/modules/blog/application/use_cases/blog_use_cases.py
from uuid import UUID
from typing import Optional

from app.core.pagination.offset import PaginatedResult
from app.modules.blog.domain.models import Blog
from app.modules.blog.interfaces.blog_repository import BlogRepositoryInterface
from app.modules.blog.application.schemas.blog_schema import (
    BlogCreateCmd,
    BlogListItemDTO,
    BlogUpdateCmd,
    BlogReadDTO,
    BlogListPage,
)


class GetBlogByIdUseCase:
    def __init__(self, repo: BlogRepositoryInterface):
        self.repo = repo

    async def execute(self, blog_id: UUID) -> Optional[BlogReadDTO]:
        entity = await self.repo.get(blog_id)
        if not entity:
            return None
        return BlogReadDTO.model_validate(entity)


class GetBlogBySlugUseCase:
    def __init__(self, repo: BlogRepositoryInterface):
        self.repo = repo

    async def execute(self, slug: str) -> Optional[BlogReadDTO]:
        entity = await self.repo.get_by_field("slug", slug)
        if not entity:
            return None
        return BlogReadDTO.model_validate(entity)


class ListBlogsUseCase:
    def __init__(self, repo: BlogRepositoryInterface):
        self.repo = repo

    async def execute(
        self,
        *,
        limit: int,
        skip: int,
        search: str | None = None,
        category: str | None = None,
        enable: bool | None = None,
    ) -> BlogListPage:
        raw = await self.repo.list_filtered(
            limit=limit,
            offset=skip,
            search=search,
            category=category,
            enable=enable,
        )
        if isinstance(raw, PaginatedResult):
            items = [BlogListItemDTO.model_validate(x) for x in raw.items]
            return BlogListPage(
                items=items,
                total=raw.total,
                skip=raw.skip,
                limit=raw.limit,
                has_next=raw.has_next,
                has_previous=raw.has_previous,
            )
        items = [BlogListItemDTO.model_validate(x) for x in raw]
        return BlogListPage(
            items=items,
            total=len(items),
            skip=skip,
            limit=limit,
            has_next=False,
            has_previous=skip > 0 and len(items) > 0,
        )


class CreateBlogUseCase:
    def __init__(self, repo: BlogRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: BlogCreateCmd) -> BlogReadDTO:
        # Check if slug is already taken
        existing = await self.repo.get_by_field("slug", cmd.slug)
        if existing:
            raise ValueError(f"A blog post with slug '{cmd.slug}' already exists.")

        if cmd.public_id:
            existing_pub = await self.repo.get_by_field("public_id", cmd.public_id)
            if existing_pub:
                raise ValueError(f"A blog post with public_id '{cmd.public_id}' already exists.")

        entity = Blog(
            title=cmd.title,
            slug=cmd.slug,
            excerpt=cmd.excerpt,
            content=cmd.content,
            category=cmd.category,
            public_id=cmd.public_id,
            read_time=cmd.read_time,
            date=cmd.date,
            language=cmd.language,
            enable=cmd.enable,
        )
        try:
            saved = await self.repo.add(entity)
            await self.repo.commit()
            await self.repo.refresh(saved)
            return BlogReadDTO.model_validate(saved)
        except Exception as e:
            await self.repo.rollback()
            raise e


class UpdateBlogUseCase:
    def __init__(self, repo: BlogRepositoryInterface):
        self.repo = repo

    async def execute(self, cmd: BlogUpdateCmd) -> Optional[BlogReadDTO]:
        entity = await self.repo.get(cmd.id)
        if not entity:
            return None

        # Check slug uniqueness if it changes
        if cmd.slug is not None and cmd.slug != entity.slug:
            existing = await self.repo.get_by_field("slug", cmd.slug)
            if existing:
                raise ValueError(f"A blog post with slug '{cmd.slug}' already exists.")

        # Check public_id uniqueness if it changes
        if cmd.public_id is not None and cmd.public_id != entity.public_id:
            existing_pub = await self.repo.get_by_field("public_id", cmd.public_id)
            if existing_pub:
                raise ValueError(f"A blog post with public_id '{cmd.public_id}' already exists.")

        if cmd.title is not None:
            entity.title = cmd.title
        if cmd.slug is not None:
            entity.slug = cmd.slug
        if cmd.excerpt is not None:
            entity.excerpt = cmd.excerpt
        if cmd.content is not None:
            entity.content = cmd.content
        if cmd.category is not None:
            entity.category = cmd.category
        if cmd.public_id is not None:
            entity.public_id = cmd.public_id
        if cmd.read_time is not None:
            entity.read_time = cmd.read_time
        if cmd.date is not None:
            entity.date = cmd.date
        if cmd.language is not None:
            entity.language = cmd.language
        if cmd.enable is not None:
            entity.enable = cmd.enable

        try:
            updated = await self.repo.update(entity)
            await self.repo.commit()
            await self.repo.refresh(updated)
            return BlogReadDTO.model_validate(updated)
        except Exception as e:
            await self.repo.rollback()
            raise e


class DeleteBlogUseCase:
    def __init__(self, repo: BlogRepositoryInterface):
        self.repo = repo

    async def execute(self, blog_id: UUID) -> bool:
        try:
            res = await self.repo.delete(blog_id)
            await self.repo.commit()
            return res.get("status", False)
        except Exception as e:
            await self.repo.rollback()
            raise e
