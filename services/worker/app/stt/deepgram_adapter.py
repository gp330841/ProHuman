from __future__ import annotations

import asyncio
from typing import Any

from deepgram import DeepgramClient, PrerecordedOptions
import structlog

from packages.contracts.transcription import TranscriptSegment, WordTimestamp
from app.stt.base import BaseSTTAdapter, STTResult

logger = structlog.get_logger(__name__)

class DeepgramAdapter(BaseSTTAdapter):
    name: str = 'deepgram'

    def __init__(self, api_key: str):
        self.api_key = api_key
        # Setting up deepgram client
        self.client = DeepgramClient(api_key)

    async def transcribe(self, audio_url: str, config: dict[str, Any] | None = None) -> STTResult:
        logger.info("transcribing_with_deepgram", audio_url=audio_url)
        options = PrerecordedOptions(
            model='nova-2',
            diarize=True,
            smart_format=True,
            utterances=True,
            punctuate=True
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
                
                for u in utterances:
                    speaker_id = str(u.get("speaker", 0))
                    speaker_set.add(speaker_id)
                    
                    words = []
                    for w in u.get("words", []):
                        words.append(WordTimestamp(
                            word=w.get("word", ""),
                            start_time=float(w.get("start", 0)),
                            end_time=float(w.get("end", 0)),
                            confidence=float(w.get("confidence", 0.0))
                        ))
                    
                    segments.append(TranscriptSegment(
                        speaker_id=speaker_id,
                        text=u.get("transcript", ""),
                        start_time=float(u.get("start", 0)),
                        end_time=float(u.get("end", 0)),
                        words=words
                    ))
                
                metadata = raw_data.get("metadata", {})
                duration = float(metadata.get("duration", 0))
                
                return STTResult(
                    segments=segments,
                    language='en',
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
        try:
            # Perform a simple ping or project check
            # For Deepgram, listing projects is a good health check
            await self.client.manage.asyncprojects.get()
            return True
        except Exception as e:
            logger.error("deepgram_health_check_failed", error=str(e))
            return False
