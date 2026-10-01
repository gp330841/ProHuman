from __future__ import annotations

import time
from typing import Any

import structlog

from packages.contracts.features import SentimentResult
from app.features.base import BaseFeatureProvider
from app.features.registry import FeatureRegistry
from app.llm.client import LLMClient

logger = structlog.get_logger(__name__)

@FeatureRegistry.register
class SentimentProvider(BaseFeatureProvider):
    name: str = 'sentiment'

    def __init__(self):
        self.llm_client = LLMClient()

    async def process(self, session_id: str, transcript_data: dict[str, Any]) -> SentimentResult:
        start_time = time.time()
        
        segments = transcript_data.get('transcript', [])
        transcript_text = "\n".join([
            f"Speaker {seg.speaker_label}: {seg.text}" for seg in segments
        ])

        messages = [
            {
                "role": "system",
                "content": "You are a sentiment analysis engine. Analyze the per-speaker sentiment and the overall conversation tone."
            },
            {
                "role": "user",
                "content": f"Analyze the sentiment of this conversation:\n\n{transcript_text}"
            }
        ]

        result = await self.llm_client.generate_structured(
            messages=messages,
            response_model=SentimentResult
        )

        elapsed = time.time() - start_time
        logger.info("sentiment_processed", session_id=session_id, elapsed=elapsed)
        
        return result
