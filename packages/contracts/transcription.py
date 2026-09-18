from __future__ import annotations

from uuid import UUID
from pydantic import BaseModel, Field

class WordTimestamp(BaseModel):
    word: str
    start: float
    end: float
    confidence: float | None = None
    speaker: int | None = None

class TranscriptSegment(BaseModel):
    segment_index: int
    speaker_label: str
    text: str
    start_time: float
    end_time: float
    confidence: float | None = None
    words: list[WordTimestamp] = Field(default_factory=list)

class TranscriptionResult(BaseModel):
    session_id: UUID
    segments: list[TranscriptSegment]
    language: str = "en"
    duration_seconds: float
    speaker_count: int
    adapter_used: str
