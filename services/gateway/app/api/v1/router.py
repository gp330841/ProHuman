from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.audio import router as audio_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.search import router as search_router
from app.api.v1.export import router as export_router
from app.api.v1.lifecycle import router as lifecycle_router
from app.api.v1.languages import router as languages_router
from app.api.v1.system import router as system_router
from app.api.v1.agent import router as agent_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(audio_router, prefix="/audio", tags=["audio"])
api_router.include_router(sessions_router, prefix="/sessions", tags=["sessions"])
api_router.include_router(search_router, prefix="/search", tags=["search"])
api_router.include_router(export_router, prefix="/export", tags=["export"])
api_router.include_router(lifecycle_router, tags=["lifecycle"])
api_router.include_router(languages_router, prefix="/languages", tags=["languages"])
api_router.include_router(system_router, prefix="/system", tags=["system"])
api_router.include_router(agent_router, prefix="/agent", tags=["agent"])

__all__ = ["api_router"]
