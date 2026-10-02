"""
Transcription data contracts.

Defines schemas for speech-to-text outputs, including word-level
timestamps, speaker diarization, and confidence scores.
"""
from __future__ import annotations

from uuid import UUID
from pydantic import BaseModel, Field

class WordTimestamp(BaseModel):
    """Timing and confidence data for a single transcribed word."""
    word: str = Field(description="The transcribed word")
    start: float = Field(description="Start time in seconds")
    end: float = Field(description="End time in seconds")
    confidence: float | None = Field(default=None, description="Transcription confidence (0-1)")
    speaker: int | None = Field(default=None, description="Speaker identifier if diarization is enabled")

class TranscriptSegment(BaseModel):
    """A contiguous segment of speech from a single speaker."""
    segment_index: int = Field(description="Sequential index of this segment")
    speaker_label: str = Field(description="Label identifying the speaker (e.g., SPEAKER_00)")
    text: str = Field(description="The transcribed text for this segment")
    start_time: float = Field(description="Segment start time in seconds")
    end_time: float = Field(description="Segment end time in seconds")
    confidence: float | None = Field(default=None, description="Average confidence for the segment")
    words: list[WordTimestamp] = Field(default_factory=list, description="Word-level details")

class TranscriptionResult(BaseModel):
    """The complete transcription result for a session."""
    session_id: UUID = Field(description="ID of the transcribed session")
    segments: list[TranscriptSegment] = Field(description="List of transcript segments")
    language: str = Field(default="en", description="Detected or specified language code")
    duration_seconds: float = Field(description="Total duration of transcribed audio")
    speaker_count: int = Field(description="Number of unique speakers detected")
    adapter_used: str = Field(description="The speech-to-text engine used")
