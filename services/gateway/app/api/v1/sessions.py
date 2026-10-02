from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from redis.asyncio import Redis

from app.dependencies import get_redis, get_session_repo, get_transcript_repo
from app.config import get_settings
from packages.contracts.sessions import SessionCreate, SessionResponse, SessionDetail, SessionListResponse
from packages.contracts.hinglish import devanagari_to_hinglish
from packages.db.repositories.session_repo import SessionRepository
from packages.db.repositories.transcript_repo import TranscriptRepository
from packages.db.models.session import SessionStatusEnum, Session
from app.services.task_dispatcher import TaskDispatcher
from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter()


class FeatureRequest(BaseModel):
    feature_names: list[str] = Field(default_factory=lambda: ["mom"])
    force: bool = False


class TranscriptSegmentInput(BaseModel):
    text: str
    speaker_name: str | None = None
    speaker_label: str | None = None
    start_time: float = 0.0
    end_time: float = 0.0
    confidence: float = 1.0


class SubmitTranscriptRequest(BaseModel):
    segments: list[TranscriptSegmentInput]


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    session_data: SessionCreate,
    session_repo: SessionRepository = Depends(get_session_repo)
) -> Any:
    """Create a new session."""
    session = await session_repo.create(
        device_id=session_data.device_id,
        audio_format=session_data.audio_format.value if hasattr(session_data.audio_format, 'value') else session_data.audio_format,
        sample_rate=session_data.sample_rate,
        metadata_=session_data.metadata or {}
    )
    return session

@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: UUID,
    session_repo: SessionRepository = Depends(get_session_repo)
) -> Any:
    """Get session detail."""
    session = await session_repo.get_with_details(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return SessionDetail(
        id=session.id,
        device_id=session.device_id,
        status=session.status,
        created_at=session.created_at,
        updated_at=session.updated_at,
        audio_format=session.audio_format,
        duration_seconds=session.duration_seconds,
        transcript_segment_count=len(session.transcript_segments) if session.transcript_segments else 0,
        transcript_segments=[
            {
                "id": str(segment.id),
                "speaker_label": segment.speaker_label,
                "text": segment.text,
                "start_time": segment.start_time,
                "end_time": segment.end_time,
                "confidence": segment.confidence,
            }
            for segment in session.transcript_segments or []
        ],
        feature_results={
            feature_name: result.data
            for feature_name, result in {
                feature.feature_name: feature
                for feature in sorted(
                    session.feature_results or [],
                    key=lambda item: item.version,
                )
            }.items()
        },
        s3_key=session.s3_key
    )


@router.post("/{session_id}/features", status_code=202)
async def generate_features(
    session_id: UUID,
    request: FeatureRequest,
    redis: Redis = Depends(get_redis),
    session_repo: SessionRepository = Depends(get_session_repo),
) -> dict[str, str]:
    session = await session_repo.get_with_details(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.transcript_segments:
        raise HTTPException(status_code=409, detail="Session has no transcript to analyze")

    dispatcher = TaskDispatcher(redis, get_settings().redis_url)
    await dispatcher.dispatch_feature_pipeline(
        str(session_id),
        request.feature_names,
        force=request.force,
    )
    return {"session_id": str(session_id), "status": "queued"}


@router.post("/{session_id}/transcript", status_code=201)
async def submit_transcript(
    session_id: UUID,
    request: SubmitTranscriptRequest,
    transcript_repo: TranscriptRepository = Depends(get_transcript_repo),
    session_repo: SessionRepository = Depends(get_session_repo),
    redis: Redis = Depends(get_redis),
) -> dict[str, Any]:
    session = await session_repo.get_with_details(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    segment_dicts = [
        {
            "session_id": session_id,
            "segment_index": idx,
            "speaker_label": seg.speaker_name or seg.speaker_label or f"speaker_0",
            "text": devanagari_to_hinglish(seg.text),
            "start_time": seg.start_time,
            "end_time": seg.end_time,
            "confidence": seg.confidence,
            "word_timestamps": [],
        }
        for idx, seg in enumerate(request.segments)
    ]
    created = await transcript_repo.bulk_create(segment_dicts)
    await session_repo.update_status(session_id, SessionStatusEnum.TRANSCRIBED)

    # Automatically trigger feature pipeline (MOM, action items, summary)
    try:
        dispatcher = TaskDispatcher(redis, get_settings().redis_url)
        await dispatcher.dispatch_feature_pipeline(str(session_id), ["mom", "action_items", "summary"], force=True)
    except Exception as e:
        logger.warning("could_not_dispatch_feature_pipeline", error=str(e))

    return {"session_id": str(session_id), "segment_count": len(created), "status": "TRANSCRIBED"}

@router.get("", response_model=SessionListResponse)
async def list_sessions(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: SessionStatusEnum | None = None,
    user_id: str | None = None,
    device_id: str | None = None,
    session_repo: SessionRepository = Depends(get_session_repo)
) -> Any:
    sessions, total_count = await session_repo.list_sessions(
        limit=limit,
        offset=offset,
        status_filter=status,
        device_id_filter=device_id,
        user_id_filter=user_id,
    )
    return SessionListResponse(
        sessions=[SessionResponse.model_validate(s) for s in sessions],
        total_count=total_count,
        limit=limit,
        offset=offset
    )

@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: UUID,
    update_data: dict[str, Any],
    session_repo: SessionRepository = Depends(get_session_repo)
) -> Any:
    """Update session metadata."""
    session = await session_repo.update(session_id, **update_data)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

__all__ = ["router"]
