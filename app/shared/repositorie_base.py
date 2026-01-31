from __future__ import annotations

from app.core.pagination.offset import PageParams, PaginatedResult
from app.shared.query_filter import FilterSchema, OperationEnum, OperatorEnum, QueryFilter

from typing import Any, Generic, TypeVar, Type, Optional, List, Sequence, Union
from uuid import UUID

from sqlalchemy import desc, asc, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

T = TypeVar("T")

class BaseAsyncRepository(Generic[T]):
    """Repositorio base asíncrono con operaciones CRUD genéricas."""

    def __init__(self, model: Type[T], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    async def get(
        self,
        id: UUID,
        *,
        eager_options: Sequence | None = None,
    ) -> Optional[T]:
        """Obtiene una entidad por id (que no esté *deleted*)."""
        stmt = select(self.model).where(
            self.model.id == id, self.model.deleted.is_(False)
        )
        if eager_options:
            stmt = stmt.options(*eager_options)
        
        result = await self.session.execute(stmt)
        
        if eager_options:
            return result.unique().scalar_one_or_none()
        else:
            return result.scalar_one_or_none()
    
    async def list(
        self,
        query_filter: QueryFilter | None = None,
        eager_options: Sequence | None = None,
        default_sort_direction: str = "desc",
        limit: int | None = None,
        offset: int | None = None,
    ) -> Union[List[T], PaginatedResult[T]]:
        """Lista entidades con soporte inteligente para paginación."""
        
        if query_filter is None:
            query_filter = QueryFilter()
        
        has_pagination = limit is not None or offset is not None
        if has_pagination:
            query_filter.pagination = PageParams(
                skip=offset or 0,
                limit=limit or 20
            )
            query_filter.pagination.validate_limit()
        
        if eager_options:
            existing_options = query_filter.eager_options or []
            query_filter.eager_options = existing_options + list(eager_options)

        if not query_filter.order_by and hasattr(self.model, 'created_at'):
            query_filter.order_by = [("created_at", default_sort_direction)]

        if has_pagination:
            return await self._execute_paginated_query(query_filter)
        else:
            return await self._execute_simple_query(query_filter)

    async def _execute_simple_query(self, query_filter: QueryFilter) -> List[T]:
        """Ejecuta consulta simple optimizada sin COUNT."""
        stmt = select(self.model)
        stmt = query_filter.apply(stmt, self.model)
        
        if query_filter.eager_options:
            stmt = stmt.options(*query_filter.eager_options)
        
        if query_filter.pagination:
            stmt = stmt.offset(query_filter.pagination.skip).limit(query_filter.pagination.limit)
        
        result = await self.session.execute(stmt)
        
        if query_filter.eager_options:
            return result.unique().scalars().all()
        else:
            return result.scalars().all()
        
    async def _execute_paginated_query(self, query_filter: QueryFilter) -> PaginatedResult[T]:
        """Ejecuta consulta con metadata de paginación (incluye COUNT)."""
        return await query_filter.execute_paginated(self.session, self.model)

    async def count(
        self,
        query_filter: QueryFilter | None = None,
    ) -> int:
        """Cuenta entidades que coinciden con los filtros."""
        
        if query_filter:
            base_stmt = select(self.model)
            filtered_stmt = query_filter.apply(base_stmt, self.model)
            count_stmt = select(func.count()).select_from(filtered_stmt.subquery())
        else:
            count_stmt = select(func.count()).select_from(self.model).where(
                self.model.deleted.is_(False)
            )
        
        result = await self.session.execute(count_stmt)
        return result.scalar_one()

    async def exists(
        self,
        query_filter: QueryFilter | None = None,
        id: UUID | None = None,
    ) -> bool:
        """Verifica si existe al menos una entidad que coincida con los filtros."""
        
        if id:
            stmt = select(self.model.id).where(
                self.model.id == id,
                self.model.deleted.is_(False)
            ).limit(1)
        elif query_filter:
            base_stmt = select(self.model.id).limit(1)
            stmt = query_filter.apply(base_stmt, self.model)
        else:
            stmt = select(self.model.id).where(
                self.model.deleted.is_(False)
            ).limit(1)
        
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def search(
        self,
        search_term: str,
        search_fields: List[str],
        limit: int | None = None,
        offset: int | None = None,
    ) -> Union[List[T], PaginatedResult[T]]:
        """Búsqueda en múltiples campos con paginación opcional."""
        
        search_filters = [
            FilterSchema(
                field=field,
                value=search_term,
                operator=OperatorEnum.ILIKE
            )
            for field in search_fields
        ]
        
        query_filter = QueryFilter(
            filters=search_filters,
            operation=OperationEnum.OR,
        )
        
        return await self.list(
            query_filter=query_filter,
            limit=limit,
            offset=offset
        )

    async def add(self, obj: T) -> T:
        """Añade y sincroniza la entidad (obtiene PK y defaults)."""
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def update(self, obj: T) -> T:
        """Sincroniza cambios ya aplicados sobre la instancia."""
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def soft_delete(self, obj: T) -> None:
        """Marca `deleted=True` y sincroniza."""
        obj.deleted = True  # type: ignore[attr-defined]
        await self.session.flush()

    async def delete(self, id: UUID) -> dict[str, any]:
        from .delete_service import DeleteResponse
        
        entity = await self.get(id)
        if entity:
            await self.soft_delete(entity)
            return DeleteResponse(
                status=True,
                deleted_id=str(id)
            ).model_dump()
        return DeleteResponse(
            status=False,
            deleted_id=str(id)
        ).model_dump()
    
    async def hard_delete(self, id: UUID) -> dict[str, any]:
        from .delete_service import DeleteResponse

        entity = await self.get(id)

        if entity:
            await self.session.delete(entity)
            await self.session.flush()

            return DeleteResponse(
                status=True,
                deleted_id=str(id)
            ).model_dump()

        return DeleteResponse(
            status=False,
            deleted_id=str(id)
        ).model_dump()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def refresh(
        self,
        obj: T,
        *,
        attrs: List[str] | None = None,
        load_noload_relations: List[str] | None = None,
    ) -> None:
        """Sincroniza columnas y carga relaciones noload especificadas."""
        
        if not load_noload_relations:
            await self.session.refresh(obj, attribute_names=attrs)
            return
        
        try:
            await self._load_noload_relations_direct(obj, load_noload_relations)
            if attrs:
                await self.session.refresh(obj, attribute_names=attrs)
        except Exception as e:
            await self.session.refresh(obj, attribute_names=attrs)

    async def _load_noload_relations_direct(self, obj: T, relations: List[str]) -> None:
        """Carga relaciones noload usando asignación directa al __dict__."""
        from sqlalchemy import select
        from sqlalchemy.orm import class_mapper
        
        mapper = class_mapper(self.model)
        
        for relation_name in relations:
            if relation_name in mapper.relationships:
                relationship = mapper.relationships[relation_name]
                target_model = relationship.mapper.class_
                is_collection = relationship.uselist
                
                has_local_fk = False
                fk_field = None
                
                table_fks = set()
                for fk in mapper.mapped_table.foreign_keys:
                    table_fks.add(fk.parent.name)
                
                if relationship.local_columns:
                    for col in relationship.local_columns:
                        if hasattr(obj, col.name) and col.name in table_fks:
                            has_local_fk = True
                            fk_field = col.name
                            break
                
                if has_local_fk and fk_field:
                    fk_value = getattr(obj, fk_field, None)
                    if fk_value:
                        stmt = select(target_model).where(target_model.id == fk_value)
                        result = await self.session.execute(stmt)
                        related_obj = result.scalar_one_or_none()
                        if related_obj:
                            obj.__dict__[relation_name] = related_obj
                    else:
                        obj.__dict__[relation_name] = None
                else:
                    remote_columns = list(relationship.remote_side) if relationship.remote_side else []
                    if not remote_columns:
                        continue
                    
                    remote_col = remote_columns[0]
                    fk_column_name = remote_col.key
                    
                    try:
                        fk_attr = getattr(target_model, fk_column_name)
                    except AttributeError:
                        continue
                    
                    stmt = select(target_model).where(fk_attr == obj.id)
                    result = await self.session.execute(stmt)
                    
                    if is_collection:
                        related_objs = result.scalars().all()
                        obj.__dict__[relation_name] = list(related_objs)
                    else:
                        related_obj = result.scalar_one_or_none()
                        obj.__dict__[relation_name] = related_obj
    
    async def get_by_field(
        self,
        field_name: str,
        field_value: Any,
        *,
        eager_options: Sequence | None = None,
    ) -> Optional[T]:
        """Obtiene una entidad por un campo específico (que no esté deleted)."""
        field = getattr(self.model, field_name)
        
        stmt = select(self.model).where(
            field == field_value,
            self.model.deleted.is_(False)
        )
        
        if eager_options:
            stmt = stmt.options(*eager_options)
        
        result = await self.session.execute(stmt)
        
        if eager_options:
            return result.unique().scalar_one_or_none()
        else:
            return result.scalar_one_or_none()
