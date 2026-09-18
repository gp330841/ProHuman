from __future__ import annotations

from typing import Any

from app.stt.base import BaseSTTAdapter, STTResult

class WhisperXAdapter(BaseSTTAdapter):
    """
    WhisperX Adapter for STT.
    This is a Phase 2 feature due to GPU requirements.
    """
    name: str = 'whisperx'

    async def transcribe(self, audio_url: str, config: dict[str, Any] | None = None) -> STTResult:
        raise NotImplementedError("WhisperX adapter requires GPU resources and is a Phase 2 feature.")

    async def health_check(self) -> bool:
        return False
