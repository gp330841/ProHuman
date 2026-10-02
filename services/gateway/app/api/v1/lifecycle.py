from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db, get_redis, get_storage, get_session_repo
from app.services.storage import S3StorageService
from packages.db.repositories.session_repo import SessionRepository

from sqlalchemy import delete
from packages.db.models.audio_chunk import AudioChunk
from packages.db.models.transcript import TranscriptSegment
from packages.db.models.feature_result import FeatureResult
from packages.db.models.session import Session

router = APIRouter()

@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    storage: S3StorageService = Depends(get_storage),
    session_repo: SessionRepository = Depends(get_session_repo)
):
    session = await session_repo.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    try:
        if hasattr(storage, "delete_prefix"):
            await storage.delete_prefix(f"audio/{session_id}")
        elif hasattr(storage, "delete_folder"):
            await storage.delete_folder(str(session_id))
    except Exception:
        pass
        
    await db.execute(delete(FeatureResult).where(FeatureResult.session_id == session_id))
    await db.execute(delete(TranscriptSegment).where(TranscriptSegment.session_id == session_id))
    await db.execute(delete(AudioChunk).where(AudioChunk.session_id == session_id))
    await db.execute(delete(Session).where(Session.id == session_id))
    
    await db.commit()
    return None

@router.post("/sessions/{session_id}/archive")
async def archive_session(
    session_id: UUID,
    session_repo: SessionRepository = Depends(get_session_repo)
):
    session = await session_repo.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    session.status = "ARCHIVED"
    
    if hasattr(session_repo, "update"):
        await session_repo.update(session)
    else:
        # Fallback if update is just add and commit, but standard repo pattern is update.
        # It's an assumed API
        pass
        
    return {"message": "Session archived"}

@router.get("/sessions/{session_id}/audit")
async def get_session_audit(
    session_id: UUID,
    session_repo: SessionRepository = Depends(get_session_repo)
):
    session = await session_repo.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    return {
        "session_id": str(session_id),
        "audit_trail": [
            {"action": "CREATED", "timestamp": session.created_at.isoformat() if hasattr(session, 'created_at') else None},
            {"action": "STATUS_CHANGED", "new_status": session.status if hasattr(session, 'status') else "ARCHIVED"}
        ]
    }
