"""STT base module."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel

from packages.contracts.transcription import TranscriptSegment

class STTResult(BaseModel):
    """Result from STT adapter."""
    segments: list[TranscriptSegment]
    language: str = 'en'
    duration_seconds: float
    speaker_count: int
    raw_response: dict[str, Any] | None = None

class BaseSTTAdapter(ABC):
    """Base adapter for STT processing."""
    name: str
    
    @abstractmethod
    async def transcribe(self, audio_url: str, config: dict[str, Any] | None = None) -> STTResult:
        """Transcribe audio from URL."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check health of the STT service."""
        pass
