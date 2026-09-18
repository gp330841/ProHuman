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
    
    # Resources are lazy-initialized in dependencies in reality,
    # but we can do some global start up if needed here.
    
    yield
    
    await logger.ainfo("Shutting down gateway service...")
    # Clean up resources


def create_app() -> FastAPI:
    """Factory to create the FastAPI application."""
    app = FastAPI(
        title="Gateway Service",
        description="Conversation Intelligence Platform Gateway",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # We add RateLimit middleware (need Redis so typically we pass it or resolve dynamically)
    # app.add_middleware(RateLimitMiddleware)
    
    setup_error_handlers(app)

    # Include routers
    app.include_router(api_router)

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "ok"}

    return app

__all__ = ["create_app"]
