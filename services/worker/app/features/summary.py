from __future__ import annotations

import time
from typing import Any

import structlog

from packages.contracts.features import SummaryResult
from app.features.base import BaseFeatureProvider
from app.features.registry import FeatureRegistry
from app.llm.client import LLMClient

logger = structlog.get_logger(__name__)

@FeatureRegistry.register
class SummaryProvider(BaseFeatureProvider):
    name: str = 'summary'

    def __init__(self):
        self.llm_client = LLMClient()

    async def process(self, session_id: str, transcript_data: dict[str, Any]) -> SummaryResult:
        start_time = time.time()
        
        segments = transcript_data.get('transcript', [])
        transcript_text = "\n".join([
            f"Speaker {seg.speaker_id}: {seg.text}" for seg in segments
        ])

        messages = [
            {
                "role": "system",
                "content": "You are an expert meeting summarizer. Extract a concise title, an executive summary, and key topics discussed."
            },
            {
                "role": "user",
                "content": f"Please summarize this transcript:\n\n{transcript_text}"
            }
        ]

        result = await self.llm_client.generate_structured(
            messages=messages,
            response_model=SummaryResult
        )

        elapsed = time.time() - start_time
        logger.info("summary_processed", session_id=session_id, elapsed=elapsed)
        
        return result
