"""
Session-related data contracts.

Defines schemas for audio session creation, status tracking, and details.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field
from .audio import AudioFormat

class SessionStatus(str, Enum):
    """Lifecycle status of a session."""
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
    """Request payload to create a new session."""
    device_id: str = Field(description="Identifier of the recording device")
    audio_format: AudioFormat = Field(description="Format of the incoming audio")
    sample_rate: int = Field(default=16000, description="Audio sample rate")
    language: str = Field(default='auto', description="Expected language or 'auto'")
    metadata: dict[str, Any] | None = Field(default=None, description="Optional custom metadata")

class SessionResponse(BaseModel):
    """Basic session details returned to clients."""
    model_config = {"from_attributes": True}

    id: UUID = Field(description="Unique session identifier")
    device_id: str = Field(description="Identifier of the recording device")
    status: SessionStatus = Field(description="Current status of the session")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    audio_format: str | None = Field(default=None, description="Audio format used")
    duration_seconds: float | None = Field(default=None, description="Total duration if known")
    language: str | None = Field(default=None, description="Detected or specified language")

class SessionDetail(SessionResponse):
    """Detailed session representation including transcript and features."""
    transcript_segment_count: int = Field(default=0, description="Number of transcript segments")
    transcript_segments: list[dict[str, Any]] = Field(default_factory=list, description="List of segments")
    feature_results: dict[str, Any] = Field(default_factory=dict, description="Extracted AI features")
    s3_key: str | None = Field(default=None, description="Storage key for the raw audio")

class SessionListResponse(BaseModel):
    """Paginated list of sessions."""
    sessions: list[SessionResponse] = Field(description="List of sessions")
    total_count: int = Field(description="Total number of sessions matching criteria")
    limit: int = Field(description="Pagination limit")
    offset: int = Field(description="Pagination offset")
