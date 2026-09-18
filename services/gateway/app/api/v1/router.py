from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.audio import router as audio_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.search import router as search_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(audio_router, prefix="/audio", tags=["audio"])
api_router.include_router(sessions_router, prefix="/sessions", tags=["sessions"])
api_router.include_router(search_router, prefix="/search", tags=["search"])

__all__ = ["api_router"]
