# app/modules/blog/infrastructure/__init__.py
from app.modules.blog.infrastructure.repository import SQLAlchemyBlogRepository

__all__ = ["SQLAlchemyBlogRepository"]
