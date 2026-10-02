"""Module for deepgram_adapter.py."""
from __future__ import annotations

import asyncio
from typing import Any

from deepgram import DeepgramClient, PrerecordedOptions
import structlog

from packages.contracts.transcription import TranscriptSegment, WordTimestamp
from app.stt.base import BaseSTTAdapter, STTResult

logger = structlog.get_logger(__name__)

class DeepgramAdapter(BaseSTTAdapter):
    """Class documentation."""
    name: str = 'deepgram'

    SUPPORTED_LANGUAGES: dict[str, str] = {
        "en": "English",
        "hi": "Hindi",
        "es": "Spanish",
        "fr": "French",
        "de": "German",
        "ja": "Japanese",
        "ko": "Korean",
        "zh": "Chinese",
        "pt": "Portuguese",
        "ar": "Arabic",
        "ru": "Russian",
        "it": "Italian",
        "nl": "Dutch",
        "pl": "Polish",
        "sv": "Swedish",
        "tr": "Turkish",
        "id": "Indonesian",
        "da": "Danish",
        "el": "Greek",
        "th": "Thai"
    }

    def __init__(self, api_key: str):
        """Method documentation."""
        self.api_key = api_key
        # Setting up deepgram client
        self.client = DeepgramClient(api_key)

    async def transcribe(self, audio_url: str, config: dict[str, Any] | None = None) -> STTResult:
        """Method documentation."""
        logger.info("transcribing_with_deepgram", audio_url=audio_url)
        language_config = (config or {}).get('language', 'auto')
        options = PrerecordedOptions(
            model='nova-2',
            diarize=True,
            smart_format=True,
            utterances=True,
            punctuate=True,
            detect_language=True if language_config == 'auto' else False,
            language=None if language_config == 'auto' else language_config,
        )

        for attempt in range(3):
            try:
                # Wrap the synchronous SDK call in an executor if needed, 
                # but deepgram-sdk usually provides an async client as well via `DeepgramClient` 
                # Actually, in deepgram-sdk>=3.4, you can do:
                # response = await self.client.listen.asyncprerecorded.v("1").transcribe_url({"url": audio_url}, options)
                
                # Assuming standard async usage for Deepgram SDK >= 3.4
                response = await self.client.listen.asyncprerecorded.v("1").transcribe_url(
                    {"url": audio_url},
                    options
                )
                
                raw_data = response.to_dict()
                results = raw_data.get("results", {})
                utterances = results.get("utterances", [])
                
                segments = []
                speaker_set = set()
                
                for segment_index, u in enumerate(utterances):
                    speaker_id = str(u.get("speaker", 0))
                    speaker_set.add(speaker_id)
                    
                    words = []
                    for w in u.get("words", []):
                        words.append(WordTimestamp(
                            word=w.get("word", ""),
                            start=float(w.get("start", 0)),
                            end=float(w.get("end", 0)),
                            confidence=float(w.get("confidence", 0.0))
                        ))
                    
                    segments.append(TranscriptSegment(
                        segment_index=segment_index,
                        speaker_label=f"speaker_{speaker_id}",
                        text=u.get("transcript", ""),
                        start_time=float(u.get("start", 0)),
                        end_time=float(u.get("end", 0)),
                        words=words
                    ))
                
                metadata = raw_data.get("metadata", {})
                duration = float(metadata.get("duration", 0))
                detected_lang = metadata.get('detected_language', language_config if language_config != 'auto' else 'en')
                
                return STTResult(
                    segments=segments,
                    language=detected_lang,
                    duration_seconds=duration,
                    speaker_count=len(speaker_set),
                    raw_response=raw_data
                )
            except Exception as e:
                logger.error("deepgram_transcription_failed", attempt=attempt, error=str(e))
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)

    async def health_check(self) -> bool:
        """Method documentation."""
        try:
            # Perform a simple ping or project check
            # For Deepgram, listing projects is a good health check
            await self.client.manage.asyncprojects.get()
            return True
        except Exception as e:
            logger.error("deepgram_health_check_failed", error=str(e))
            return False
