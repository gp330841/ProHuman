from __future__ import annotations

from typing import Generic, Sequence, TypeVar
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from ..base import Base

T = TypeVar("T", bound=Base)

class BaseRepository(Generic[T]):
    def __init__(self, session: AsyncSession, model_class: type[T]):
        self.session = session
        self.model_class = model_class

    async def create(self, **kwargs) -> T:
        instance = self.model_class(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def get_by_id(self, id: UUID) -> T | None:
        return await self.session.get(self.model_class, id)

    async def list(self, limit: int = 20, offset: int = 0, **filters) -> list[T]:
        stmt = select(self.model_class).filter_by(**filters).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, id: UUID, **kwargs) -> T | None:
        instance = await self.get_by_id(id)
        if instance:
            for key, value in kwargs.items():
                setattr(instance, key, value)
            await self.session.flush()
        return instance

    async def delete(self, id: UUID) -> bool:
        instance = await self.get_by_id(id)
        if instance:
            await self.session.delete(instance)
            await self.session.flush()
            return True
        return False

    async def count(self, **filters) -> int:
        stmt = select(func.count()).select_from(self.model_class).filter_by(**filters)
        result = await self.session.execute(stmt)
        return result.scalar_one()
