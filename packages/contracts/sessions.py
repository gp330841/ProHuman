from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID
from pydantic import BaseModel
from .audio import AudioFormat

class SessionStatus(str, Enum):
    CREATED = "CREATED"
    RECORDING = "RECORDING"
    PROCESSING = "PROCESSING"
    TRANSCRIBING = "TRANSCRIBING"
    TRANSCRIBED = "TRANSCRIBED"
    INDEXING = "INDEXING"
    INDEXED = "INDEXED"
    EXTRACTING = "EXTRACTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class SessionCreate(BaseModel):
    device_id: str
    audio_format: AudioFormat
    sample_rate: int = 16000
    metadata: dict[str, Any] | None = None

class SessionResponse(BaseModel):
    id: UUID
    device_id: str
    status: SessionStatus
    created_at: datetime
    updated_at: datetime
    audio_format: str | None = None
    duration_seconds: float | None = None

class SessionDetail(SessionResponse):
    transcript_segment_count: int = 0
    feature_results: list[str] = []
    s3_key: str | None = None

class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    total_count: int
    limit: int
    offset: int
