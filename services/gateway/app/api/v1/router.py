from __future__ import annotations

from fastapi import APIRouter, Depends

from packages.access import Principal, require_admin, require_member, require_principal

from app.api.v1.audio import router as audio_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.search import router as search_router
from app.api.v1.export import router as export_router
from app.api.v1.lifecycle import router as lifecycle_router
from app.api.v1.languages import router as languages_router
from app.api.v1.system import router as system_router
from app.api.v1.agent import router as agent_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(audio_router, prefix="/audio", tags=["audio"], dependencies=[Depends(require_principal)])
api_router.include_router(sessions_router, prefix="/sessions", tags=["sessions"], dependencies=[Depends(require_principal)])
api_router.include_router(search_router, prefix="/search", tags=["search"], dependencies=[Depends(require_member)])
api_router.include_router(export_router, prefix="/export", tags=["export"], dependencies=[Depends(require_member)])
api_router.include_router(lifecycle_router, tags=["lifecycle"], dependencies=[Depends(require_member)])
api_router.include_router(languages_router, prefix="/languages", tags=["languages"])
api_router.include_router(system_router, prefix="/system", tags=["system"], dependencies=[Depends(require_admin)])
api_router.include_router(agent_router, prefix="/agent", tags=["agent"])

@api_router.get("/me")
async def get_identity(principal: Principal = Depends(require_principal)) -> Principal:
    return principal


__all__ = ["api_router"]
