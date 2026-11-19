from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db, get_redis, get_storage, get_session_repo
from packages.access import Principal, require_member
from app.services.storage import S3StorageService
from packages.db.repositories.session_repo import SessionRepository

from sqlalchemy import delete
from packages.db.models.audio_chunk import AudioChunk
from packages.db.models.transcript import TranscriptSegment
from packages.db.models.feature_result import FeatureResult
from packages.db.models.session import Session

router = APIRouter()
logger = structlog.get_logger(__name__)

@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: UUID,
    principal: Principal = Depends(require_member),
    db: AsyncSession = Depends(get_db),
    storage: S3StorageService = Depends(get_storage),
    session_repo: SessionRepository = Depends(get_session_repo)
):
    session = await session_repo.get_for_update(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    await storage.delete_recording(str(session_id))
        
    await db.execute(delete(FeatureResult).where(FeatureResult.session_id == session_id))
    await db.execute(delete(TranscriptSegment).where(TranscriptSegment.session_id == session_id))
    await db.execute(delete(AudioChunk).where(AudioChunk.session_id == session_id))
    await db.execute(delete(Session).where(Session.id == session_id))
    
    await db.commit()
    logger.info('recording_deleted', session_id=str(session_id), user_id=principal.user_id, workspace_id=str(principal.workspace_id))
    return None

@router.post("/sessions/{session_id}/archive")
async def archive_session(
    session_id: UUID,
    session_repo: SessionRepository = Depends(get_session_repo)
):
    session = await session_repo.get_for_update(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.metadata_ = {**(session.metadata_ or {}), "archived_at": datetime.now(timezone.utc).isoformat()}
    await session_repo.session.commit()
    return {"message": "Session archived"}

@router.get("/sessions/{session_id}/audit")
async def get_session_audit(
    session_id: UUID,
    session_repo: SessionRepository = Depends(get_session_repo)
):
    session = await session_repo.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    events = [{"action": "CREATED", "timestamp": session.created_at.isoformat()}]
    if archived_at := (session.metadata_ or {}).get("archived_at"):
        events.append({"action": "ARCHIVED", "timestamp": archived_at})
    return {"session_id": str(session_id), "audit_trail": events}
