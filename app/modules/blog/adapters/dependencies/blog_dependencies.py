# app/modules/blog/adapters/dependencies/blog_dependencies.py
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.modules.blog.interfaces.blog_repository import BlogRepositoryInterface
from app.modules.blog.infrastructure.repository import SQLAlchemyBlogRepository
from app.modules.blog.application.use_cases import (
    GetBlogByIdUseCase,
    GetBlogBySlugUseCase,
    ListBlogsUseCase,
    CreateBlogUseCase,
    UpdateBlogUseCase,
    DeleteBlogUseCase,
)


def get_blog_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BlogRepositoryInterface:
    return SQLAlchemyBlogRepository(db)


def get_blog_by_id_uc(
    repo: Annotated[BlogRepositoryInterface, Depends(get_blog_repository)],
) -> GetBlogByIdUseCase:
    return GetBlogByIdUseCase(repo)


def get_blog_by_slug_uc(
    repo: Annotated[BlogRepositoryInterface, Depends(get_blog_repository)],
) -> GetBlogBySlugUseCase:
    return GetBlogBySlugUseCase(repo)


def list_blogs_uc(
    repo: Annotated[BlogRepositoryInterface, Depends(get_blog_repository)],
) -> ListBlogsUseCase:
    return ListBlogsUseCase(repo)


def create_blog_uc(
    repo: Annotated[BlogRepositoryInterface, Depends(get_blog_repository)],
) -> CreateBlogUseCase:
    return CreateBlogUseCase(repo)


def update_blog_uc(
    repo: Annotated[BlogRepositoryInterface, Depends(get_blog_repository)],
) -> UpdateBlogUseCase:
    return UpdateBlogUseCase(repo)


def delete_blog_uc(
    repo: Annotated[BlogRepositoryInterface, Depends(get_blog_repository)],
) -> DeleteBlogUseCase:
    return DeleteBlogUseCase(repo)


GetBlogByIdUseCaseDep = Annotated[GetBlogByIdUseCase, Depends(get_blog_by_id_uc)]
GetBlogBySlugUseCaseDep = Annotated[GetBlogBySlugUseCase, Depends(get_blog_by_slug_uc)]
ListBlogsUseCaseDep = Annotated[ListBlogsUseCase, Depends(list_blogs_uc)]
CreateBlogUseCaseDep = Annotated[CreateBlogUseCase, Depends(create_blog_uc)]
UpdateBlogUseCaseDep = Annotated[UpdateBlogUseCase, Depends(update_blog_uc)]
DeleteBlogUseCaseDep = Annotated[DeleteBlogUseCase, Depends(delete_blog_uc)]
