# app/core/pagination/offset.py

from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel

try:
    from pydantic.generics import GenericModel
except ImportError:
    from pydantic import BaseModel as GenericModel

T = TypeVar("T")

class PageParams(BaseModel):
    skip: int = 0
    limit: int = 20

    def validate_limit(self, max_limit: int = 100):
        if self.limit > max_limit:
            self.limit = max_limit


class PaginatedResult(BaseModel, Generic[T]):
    total: int
    items: List[T]
    skip: int
    limit: int
    has_next: bool
    has_previous: bool
