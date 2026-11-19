from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query

from packages.access import Principal, require_member, require_principal
from app.dependencies import get_session_repo, get_transcript_repo
from packages.contracts.sessions import SessionCreate, SessionResponse, SessionDetail, SessionListResponse
from packages.db.repositories.session_repo import SessionRepository
from packages.db.repositories.transcript_repo import TranscriptRepository
from packages.db.models.session import SessionStatusEnum
from packages.db.repositories.feature_repo import FeatureRepository
from packages.db.models.pipeline_job import PipelineJob
from packages.db.repositories.pipeline_repo import enqueue_stage, stage_statuses
from sqlalchemy import select
from pydantic import BaseModel, ConfigDict, Field
import structlog
router = APIRouter()
logger = structlog.get_logger(__name__)


class FeatureRequest(BaseModel):
    feature_names: list[Literal["mom", "action_items", "summary", "sentiment", "follow_up"]] = Field(default_factory=lambda: ["mom"])
    force: bool = False


class TranscriptSegmentInput(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    speaker_name: str | None = None
    speaker_label: str | None = None
    start_time: float = 0.0
    end_time: float = 0.0
    confidence: float = 1.0


class SubmitTranscriptRequest(BaseModel):
    segments: list[TranscriptSegmentInput] = Field(min_length=1, max_length=10000)


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    session_data: SessionCreate,
    principal: Principal = Depends(require_principal),
    session_repo: SessionRepository = Depends(get_session_repo)
) -> Any:
    """Create a new session."""
    if principal.device_id and session_data.device_id != principal.device_id:
        raise HTTPException(status_code=403, detail="Credential belongs to another recording device")
    session = await session_repo.create(
        device_id=session_data.device_id,
        audio_format=session_data.audio_format.value if hasattr(session_data.audio_format, 'value') else session_data.audio_format,
        sample_rate=session_data.sample_rate,
        owner_id=principal.user_id,
        metadata_={
            "language": session_data.language,
            **{key: value for key, value in (session_data.metadata or {}).items()
               if key not in {"user_id", "user_role", "workspace_id", "owner_id", "language", "archived_at"}},
        }
    )
    await session_repo.session.commit()
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
        s3_key=session.s3_key,
        mom_version=max((item.version for item in session.feature_results if item.feature_name == "mom"), default=None),
        pipeline_stages=await stage_statuses(session_repo.session, session_id)
    )


@router.post("/{session_id}/features", status_code=202, dependencies=[Depends(require_member)])
async def generate_features(
    session_id: UUID,
    request: FeatureRequest,
    session_repo: SessionRepository = Depends(get_session_repo),
) -> dict[str, str]:
    session = await session_repo.get_for_update(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status in {SessionStatusEnum.CREATED, SessionStatusEnum.PROCESSING, SessionStatusEnum.RECORDING, SessionStatusEnum.FAILED}:
        raise HTTPException(status_code=409, detail="Session has no transcript to analyze")

    names = sorted(set(request.feature_names))
    key = str(uuid4()) if request.force else "requested:" + ",".join(names)
    await enqueue_stage(
        session_repo.session, session_id, "features", run_key=key,
        feature_names=names, force=request.force,
    )
    await session_repo.session.commit()
    return {"session_id": str(session_id), "status": "queued"}


@router.post("/{session_id}/transcript", status_code=201)
async def submit_transcript(
    session_id: UUID,
    request: SubmitTranscriptRequest,
    transcript_repo: TranscriptRepository = Depends(get_transcript_repo),
    session_repo: SessionRepository = Depends(get_session_repo),
) -> dict[str, Any]:
    session = await session_repo.get_for_update(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != SessionStatusEnum.CREATED:
        raise HTTPException(status_code=409, detail="Session already has audio or a transcript")
    if any(segment.start_time < 0 or segment.end_time < segment.start_time for segment in request.segments):
        raise HTTPException(status_code=422, detail="Invalid transcript timestamps")

    segment_dicts = [
        {
            "session_id": session_id,
            "segment_index": idx,
            "speaker_label": seg.speaker_name or seg.speaker_label or f"speaker_0",
            "text": seg.text,
            "start_time": seg.start_time,
            "end_time": seg.end_time,
            "confidence": seg.confidence,
            "word_timestamps": [],
        }
        for idx, seg in enumerate(request.segments)
    ]
    created = await transcript_repo.bulk_create(segment_dicts)
    session.status = SessionStatusEnum.TRANSCRIBED
    await enqueue_stage(session_repo.session, session_id, "embedding")
    await enqueue_stage(session_repo.session, session_id, "features")
    await session_repo.session.commit()

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

@router.patch("/{session_id}", response_model=SessionResponse, dependencies=[Depends(require_member)])
async def update_session(
    session_id: UUID,
    update_data: dict[str, Any],
    session_repo: SessionRepository = Depends(get_session_repo)
) -> Any:
    """Update session metadata."""
    if set(update_data) != {"metadata"} or not isinstance(update_data["metadata"], dict):
        raise HTTPException(status_code=422, detail="Only recording metadata can be edited")
    session = await session_repo.get_for_update(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.metadata_ = {
        **(session.metadata_ or {}),
        **{key: value for key, value in update_data["metadata"].items()
           if key not in {"user_id", "user_role", "owner_id", "workspace_id", "language", "archived_at"}},
    }
    await session_repo.session.commit()
    return session


@router.post("/{session_id}/stages/{stage}/retry", status_code=202, dependencies=[Depends(require_member)])
async def retry_stage(
    session_id: UUID,
    stage: Literal["transcription", "embedding", "features"],
    repo: SessionRepository = Depends(get_session_repo),
):
    session = await repo.get_for_update(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    job = await repo.session.scalar(
        select(PipelineJob).where(PipelineJob.session_id == session_id, PipelineJob.stage == stage)
        .order_by(PipelineJob.created_at.desc(), PipelineJob.id.desc()).limit(1).with_for_update()
    )
    if job is None or job.state not in {"failed", "queued", "dispatched"}:
        raise HTTPException(status_code=409, detail="No failed or pending stage to retry")
    if job.state == "failed":
        job.state = "queued"
        job.attempts = 0
        job.available_at = datetime.now(timezone.utc)
        if stage == "transcription":
            session.status = SessionStatusEnum.PROCESSING
    await repo.session.commit()
    return {"stage": stage, "state": job.state}


class ActionReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(gt=0)
    description: str = Field(min_length=1, max_length=2000)
    assignee: str | None = Field(None, max_length=255)
    deadline: date | None = None


@router.patch("/{session_id}/mom/action-items/{index}")
async def review_action_item(
    session_id: UUID,
    index: int,
    review: ActionReview,
    principal: Principal = Depends(require_member),
    repo: SessionRepository = Depends(get_session_repo),
):
    if not await repo.get_for_update(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    features = FeatureRepository(repo.session)
    mom = await features.get_by_session_and_name(session_id, "mom")
    if mom is None:
        raise HTTPException(status_code=404, detail="Meeting notes unavailable")
    if mom.version != review.version:
        raise HTTPException(status_code=409, detail="Meeting notes changed. Refresh before editing.")
    items = list(mom.data.get("action_items", []))
    if not 0 <= index < len(items):
        raise HTTPException(status_code=404, detail="Action item unavailable")
    changes = review.model_dump(mode="json", exclude={"version"})
    items[index] = {**items[index], **changes, "reviewed": True}
    data = {**mom.data, "action_items": items}
    result = await features.create(session_id=session_id, feature_name="mom", version=mom.version + 1, data=data)
    await repo.session.commit()
    logger.info("action_item_reviewed", workspace_id=str(principal.workspace_id),
                user_id=principal.user_id, session_id=str(session_id), index=index, version=result.version)
    return {"mom": data, "version": result.version}


__all__ = ["router"]
