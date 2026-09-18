from __future__ import annotations

import time
from typing import Any

import structlog
from pydantic import BaseModel

from packages.contracts.features import FollowUp
from app.features.base import BaseFeatureProvider
from app.features.registry import FeatureRegistry
from app.llm.client import LLMClient

logger = structlog.get_logger(__name__)

class FollowUpList(BaseModel):
    items: list[FollowUp]

@FeatureRegistry.register
class FollowUpProvider(BaseFeatureProvider):
    name: str = 'follow_up'

    def __init__(self):
        self.llm_client = LLMClient()

    async def process(self, session_id: str, transcript_data: dict[str, Any]) -> FollowUpList:
        start_time = time.time()
        
        segments = transcript_data.get('transcript', [])
        transcript_text = "\n".join([
            f"Speaker {seg.speaker_id}: {seg.text}" for seg in segments
        ])

        messages = [
            {
                "role": "system",
                "content": "Extract follow-up items, pending questions, and deferred decisions from the conversation."
            },
            {
                "role": "user",
                "content": f"Extract follow-up details from this transcript:\n\n{transcript_text}"
            }
        ]

        result = await self.llm_client.generate_structured(
            messages=messages,
            response_model=FollowUpList
        )

        elapsed = time.time() - start_time
        logger.info("follow_up_processed", session_id=session_id, elapsed=elapsed)
        
        return result
