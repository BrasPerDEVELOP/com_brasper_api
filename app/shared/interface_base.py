# app/shared/interfaces/base_repository.py
from abc import ABC, abstractmethod
from typing import Any, Dict, TypeVar, Generic, Optional, List, Union
from uuid import UUID

from sqlalchemy import Sequence

from app.core.pagination.offset import PaginatedResult
from app.shared.query_filter import QueryFilter

T = TypeVar("T")

class BaseRepositoryInterface(ABC, Generic[T]):
    
    @abstractmethod
    async def get(
        self, 
        pk: UUID, 
        *,
        eager_options: Sequence | None = None
    ) -> Optional[T]:
        raise NotImplementedError
    
    @abstractmethod
    async def list(
        self,
        query_filter: QueryFilter | None = None,
        eager_options: Sequence | None = None,
        default_sort_direction: str = "desc",
        limit: int | None = None,
        offset: int | None = None,
    ) -> Union[List[T], PaginatedResult[T]]:
        raise NotImplementedError

    @abstractmethod
    async def count(self, query_filter: QueryFilter | None = None) -> int:
        raise NotImplementedError

    @abstractmethod
    async def add(self, obj: T) -> T:
        raise NotImplementedError

    @abstractmethod
    async def update(self, obj: T) -> T:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, pk: UUID) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_field(
        self,
        field_name: str,
        field_value: Any,
        *,
        eager_options: Sequence | None = None,
    ) -> Optional[T]:
        raise NotImplementedError    

    @abstractmethod
    async def hard_delete(self, pk: UUID) -> None:
        raise NotImplementedError

    @abstractmethod
    async def commit(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def rollback(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def refresh(
        self,
        obj: T,
        *,
        attrs: List[str] | None = None,
        load_noload_relations: List[str] | None = None,
    ) -> None:
        raise NotImplementedError
