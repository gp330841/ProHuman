from __future__ import annotations

import contextlib
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

async_session_factory: async_sessionmaker[AsyncSession] | None = None

def create_db_engine(database_url: str, **kwargs) -> AsyncEngine:
    global async_session_factory
    engine_kwargs = {
        "pool_size": 20,
        "max_overflow": 10,
        "pool_pre_ping": True,
        "pool_recycle": 1800,
    }
    engine_kwargs.update(kwargs)
    engine = create_async_engine(database_url, **engine_kwargs)
    async_session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )
    return engine

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    if not async_session_factory:
        raise RuntimeError("Database engine not initialized")
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

@contextlib.asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    if not async_session_factory:
        raise RuntimeError("Database engine not initialized")
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
