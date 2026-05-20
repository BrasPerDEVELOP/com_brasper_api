# app/modules/blog/interfaces/blog_repository.py
from app.shared.interface_base import BaseRepositoryInterface
from app.modules.blog.domain.models import Blog


class BlogRepositoryInterface(BaseRepositoryInterface[Blog]):
    """Puerto de persistencia para Blog."""
    ...
