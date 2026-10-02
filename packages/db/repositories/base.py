"""
Base repository providing common CRUD operations.
"""
from __future__ import annotations

from typing import Generic, Sequence, TypeVar
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from ..base import Base

T = TypeVar("T", bound=Base)

class BaseRepository(Generic[T]):
    """
    Base generic repository for SQLAlchemy models.
    Provides basic CRUD methods and common data access patterns.
    """
    def __init__(self, session: AsyncSession, model_class: type[T]):
        """
        Initialize the repository.
        
        Args:
            session: SQLAlchemy AsyncSession.
            model_class: The model class this repository manages.
        """
        self.session = session
        self.model_class = model_class

    async def create(self, **kwargs) -> T:
        """
        Create and persist a new model instance.
        
        Args:
            **kwargs: Attributes for the new instance.
            
        Returns:
            The created model instance.
        """
        instance = self.model_class(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def get_by_id(self, id: UUID) -> T | None:
        """
        Retrieve a model instance by its ID.
        
        Args:
            id: The UUID of the instance.
            
        Returns:
            The instance if found, None otherwise.
        """
        return await self.session.get(self.model_class, id)

    async def get(self, id: UUID) -> T | None:
        """
        Alias for get_by_id. Retrieve a model instance by its ID.
        
        Args:
            id: The UUID of the instance.
            
        Returns:
            The instance if found, None otherwise.
        """
        return await self.get_by_id(id)

    async def list(self, limit: int = 20, offset: int = 0, **filters) -> list[T]:
        """
        Retrieve a paginated list of model instances matching optional filters.
        
        Note: The method name `list` shadows the built-in python `list` type.
        
        Args:
            limit: Maximum number of records to return.
            offset: Number of records to skip.
            **filters: Exact match filters applied to the query.
            
        Returns:
            A list of model instances.
        """
        stmt = select(self.model_class).filter_by(**filters).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, id: UUID, **kwargs) -> T | None:
        """
        Update an existing model instance.
        
        Args:
            id: The UUID of the instance to update.
            **kwargs: Attributes and their new values.
            
        Returns:
            The updated instance if found, None otherwise.
        """
        instance = await self.get_by_id(id)
        if instance:
            for key, value in kwargs.items():
                setattr(instance, key, value)
            await self.session.flush()
        return instance

    async def delete(self, id: UUID) -> bool:
        """
        Delete a model instance.
        
        Args:
            id: The UUID of the instance to delete.
            
        Returns:
            True if deleted, False if not found.
        """
        instance = await self.get_by_id(id)
        if instance:
            await self.session.delete(instance)
            await self.session.flush()
            return True
        return False

    async def count(self, **filters) -> int:
        """
        Count the number of instances matching optional filters.
        
        Args:
            **filters: Exact match filters.
            
        Returns:
            The total count.
        """
        stmt = select(func.count()).select_from(self.model_class).filter_by(**filters)
        result = await self.session.execute(stmt)
        return result.scalar_one()
