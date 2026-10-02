"""Main entry point for gateway service."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog
from sqlalchemy.ext.asyncio import create_async_engine

from app.api.v1.router import api_router
from app.config import get_settings
from app.middleware.error_handler import setup_error_handlers
from app.middleware.rate_limit import RateLimitMiddleware


logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan event handler for FastAPI app."""
    settings = get_settings()
    
    # Init logging
    logging.basicConfig(level=settings.log_level)
    await logger.ainfo("Starting gateway service...")
    
    engine = None
    try:
        from packages.db.engine import create_db_engine
        from packages.db.base import Base
        import packages.db.models  # noqa: F401
        from sqlalchemy import text

        engine = create_db_engine(settings.database_url)
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            await conn.run_sync(Base.metadata.create_all)
        await logger.ainfo("Database tables & pgvector initialized successfully.")
    except Exception as e:
        await logger.aerror("Database initialization notice", error=str(e))

    try:
        from app.services.storage import S3StorageService
        s3 = S3StorageService(
            endpoint_url=settings.s3_endpoint_url,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            bucket_name=settings.s3_bucket_name,
        )
        await s3.init()
        await logger.ainfo("S3 bucket verified/created successfully.")
    except Exception as e:
        await logger.aerror("S3 bucket initialization notice", error=str(e))

    yield
    
    await logger.ainfo("Shutting down gateway service...")
    if engine:
        await engine.dispose()
    # Clean up resources


def create_app() -> FastAPI:
    """Factory to create the FastAPI application."""
    settings = get_settings()
    app = FastAPI(
        title="Gateway Service",
        description="Conversation Intelligence Platform Gateway",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # We add RateLimit middleware (need Redis so typically we pass it or resolve dynamically)
    app.add_middleware(RateLimitMiddleware)
    
    setup_error_handlers(app)

    # Include routers
    app.include_router(api_router)

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "ok"}

    return app

__all__ = ["create_app"]
