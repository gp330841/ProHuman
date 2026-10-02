"""
Database engine configuration and session management.

This module provides functions for creating the SQLAlchemy asynchronous engine
and managing database sessions through dependency injection or context managers.
"""
from __future__ import annotations

import contextlib
import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

async_session_factory: async_sessionmaker[AsyncSession] | None = None

def create_db_engine(database_url: str, **kwargs) -> AsyncEngine:
    """
    Create a new SQLAlchemy asynchronous engine and initialize the session factory.

    Args:
        database_url: The database connection URL.
        **kwargs: Additional arguments to pass to create_async_engine.

    Returns:
        The configured AsyncEngine instance.
    """
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

def _ensure_engine():
    """
    Ensure the database engine and session factory are initialized.
    
    If not already initialized, it attempts to read the database URL from environment
    variables (DATABASE_URL, WORKER_DATABASE_URL, GATEWAY_DATABASE_URL).
    """
    global async_session_factory
    if async_session_factory is None:
        db_url = os.environ.get("DATABASE_URL") or os.environ.get("WORKER_DATABASE_URL") or os.environ.get("GATEWAY_DATABASE_URL")
        if db_url:
            create_db_engine(db_url)
        else:
            raise RuntimeError("Database engine not initialized and DATABASE_URL is not set")

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a database session for FastAPI dependencies.

    This function is designed to be used with FastAPI's `Depends()`. It yields
    an asynchronous session, commits the transaction if successful, or rolls back
    on exception, and finally closes the session.
    """
    _ensure_engine()
    assert async_session_factory is not None
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
    """
    Provide a standalone database session context manager.

    Unlike get_db_session, this is an asynccontextmanager meant for manual usage
    in background tasks or scripts (e.g., `async with get_db_context() as session:`).
    It similarly manages commit/rollback and cleanup logic.
    """
    _ensure_engine()
    assert async_session_factory is not None
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

