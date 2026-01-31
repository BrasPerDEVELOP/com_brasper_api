# Simplified query filter - can be expanded later
from typing import Any, List, Optional, Type, Union, Dict, TypeVar
from sqlalchemy import func, select, and_, or_, asc, desc
from sqlalchemy.sql import Select
from pydantic import BaseModel
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination.offset import PageParams, PaginatedResult

T = TypeVar("T")

class OperatorEnum(str, Enum):
    EQ = "eq"
    NEQ = "neq"
    GT = "gt"
    GTE = "gte"
    IN = "in"
    NOT_IN = "not_in"
    IS_NULL = "is_null"
    LT = "lt"
    LTE = "lte"
    LIKE = "like"
    ILIKE = "ilike"

class OperationEnum(str, Enum):
    AND = "and"
    OR = "or"

class FilterSchema(BaseModel):
    field: str
    value: Any
    operator: OperatorEnum = OperatorEnum.EQ

class QueryFilter:
    def __init__(
        self,
        filters: Optional[List[FilterSchema]] = None,
        operation: OperationEnum = OperationEnum.AND,
        order_by: Optional[List[tuple[str, str]]] = None,
        pagination: Optional[PageParams] = None,
        eager_options: Optional[List[Any]] = None,
        filter_deleted: bool = True,
    ):
        self.filters = filters or []
        self.operation = operation
        self.order_by = order_by or []
        self.pagination = pagination
        self.eager_options = eager_options or []
        self.filter_deleted = filter_deleted

    def apply(self, stmt: Select, model: Type) -> Select:
        """Aplica filtros y ordenamiento"""
        if self.filter_deleted and hasattr(model, "deleted"):
            stmt = stmt.where(model.deleted.is_(False))

        filter_conditions = []
        for f in self.filters:
            field = getattr(model, f.field, None)
            if field is None:
                continue
            condition = self._get_operator(field, f.operator, f.value)
            if condition:
                filter_conditions.append(condition)

        if filter_conditions:
            if self.operation == OperationEnum.AND:
                stmt = stmt.where(and_(*filter_conditions))
            else:
                stmt = stmt.where(or_(*filter_conditions))

        # Aplicar ordenamiento
        for field_name, direction in self.order_by:
            field = getattr(model, field_name, None)
            if field:
                if direction.lower() == "desc":
                    stmt = stmt.order_by(desc(field))
                else:
                    stmt = stmt.order_by(asc(field))

        # Aplicar eager loading
        for option in self.eager_options:
            stmt = stmt.options(option)

        return stmt

    def _get_operator(self, column, operator: OperatorEnum, value: Any):
        """Operadores de filtrado"""
        if operator == OperatorEnum.EQ:
            return column == value
        elif operator == OperatorEnum.NEQ:
            return column != value
        elif operator == OperatorEnum.GT:
            return column > value
        elif operator == OperatorEnum.GTE:
            return column >= value
        elif operator == OperatorEnum.LT:
            return column < value
        elif operator == OperatorEnum.LTE:
            return column <= value
        elif operator == OperatorEnum.IN:
            return column.in_(value)
        elif operator == OperatorEnum.NOT_IN:
            return ~column.in_(value)
        elif operator == OperatorEnum.IS_NULL:
            return column.is_(None) if value else column.is_not(None)
        elif operator == OperatorEnum.LIKE:
            return column.like(value)
        elif operator == OperatorEnum.ILIKE:
            return column.ilike(value)
        return None

    async def execute_paginated(
        self, 
        session: AsyncSession, 
        model: Type[T],
    ) -> PaginatedResult[T]:
        """Ejecuta la consulta con paginación"""
        if self.pagination:
            self.pagination.validate_limit()
        
        base_stmt = select(model)
        filtered_stmt = self.apply(base_stmt, model)
        
        # Contar total
        count_stmt = select(func.count()).select_from(filtered_stmt.subquery())
        total_result = await session.execute(count_stmt)
        total = total_result.scalar_one()
        
        # Aplicar paginación
        if self.pagination:
            filtered_stmt = filtered_stmt.offset(self.pagination.skip).limit(self.pagination.limit)
        
        result = await session.execute(filtered_stmt)
        
        if self.eager_options:
            items = result.unique().scalars().all()
        else:
            items = result.scalars().all()
        
        skip = self.pagination.skip if self.pagination else 0
        limit = self.pagination.limit if self.pagination else len(items)
        
        return PaginatedResult(
            total=total,
            items=items,
            skip=skip,
            limit=limit,
            has_next=skip + limit < total,
            has_previous=skip > 0
        )

class QueryFilterBuilder:
    """Builder para QueryFilter"""
    
    def __init__(self):
        self._filters: List[FilterSchema] = []
        self._order_by: List[tuple[str, str]] = []

    def add_filter(
        self,
        condition: bool,
        field: str,
        value: Any,
        operator: OperatorEnum = OperatorEnum.EQ,
    ) -> "QueryFilterBuilder":
        """Agrega un filtro individual"""
        if condition and value is not None:
            if isinstance(value, str) and not value.strip():
                return self
            self._filters.append(FilterSchema(field=field, operator=operator, value=value))
        return self

    def add_order_by(
        self,
        field: str,
        direction: str = "asc"
    ) -> "QueryFilterBuilder":
        """Agrega un ordenamiento"""
        self._order_by.append((field, direction))
        return self

    def build(
        self, 
        operation: OperationEnum = OperationEnum.AND,
    ) -> Optional[QueryFilter]:
        """Construye el QueryFilter final"""
        if not self._filters and not self._order_by:
            return None
        
        return QueryFilter(
            filters=self._filters, 
            operation=operation,
            order_by=self._order_by if self._order_by else None,
        )
