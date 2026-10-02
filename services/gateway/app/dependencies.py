"""Module for dependencies.py."""
from __future__ import annotations

from typing import AsyncGenerator, Any

from fastapi import Depends
from redis.asyncio import Redis, ConnectionPool
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings, Settings
from packages.db.engine import get_db_session
from packages.db.repositories.session_repo import SessionRepository
from packages.db.repositories.transcript_repo import TranscriptRepository
from app.services.storage import S3StorageService

# Global pools
_redis_pool: ConnectionPool | None = None
_s3_service: S3StorageService | None = None

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get the database session."""
    async for session in get_db_session():
        yield session

async def get_redis(settings: Settings = Depends(get_settings)) -> AsyncGenerator[Redis, None]:
    """Dependency to get Redis client."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = ConnectionPool.from_url(settings.redis_url)
    
    client = Redis(connection_pool=_redis_pool)
    try:
        yield client
    finally:
        await client.close()

async def get_storage(settings: Settings = Depends(get_settings)) -> AsyncGenerator[S3StorageService, None]:
    """Dependency to get S3 storage service."""
    global _s3_service
    if _s3_service is None:
        _s3_service = S3StorageService(
            endpoint_url=settings.s3_endpoint_url,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            bucket_name=settings.s3_bucket_name,
        )
        await _s3_service.init()
    
    yield _s3_service

def get_session_repo(db: AsyncSession = Depends(get_db)) -> SessionRepository:
    """Dependency to get SessionRepository."""
    return SessionRepository(db)

def get_transcript_repo(db: AsyncSession = Depends(get_db)) -> TranscriptRepository:
    """Dependency to get TranscriptRepository."""
    return TranscriptRepository(db)

__all__ = ["get_db", "get_redis", "get_storage", "get_session_repo", "get_transcript_repo"]
