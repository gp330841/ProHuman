from __future__ import annotations

import time
from typing import Any

import structlog

from packages.contracts.features import MOMResult
from app.features.base import BaseFeatureProvider
from app.features.registry import FeatureRegistry
from app.llm.client import LLMClient

logger = structlog.get_logger(__name__)

@FeatureRegistry.register
class MOMProvider(BaseFeatureProvider):
    name: str = 'mom'

    def __init__(self):
        self.llm_client = LLMClient()

    async def process(self, session_id: str, transcript_data: dict[str, Any]) -> MOMResult:
        start_time = time.time()
        
        segments = transcript_data.get('transcript', [])
        transcript_text = "\n".join([
            f"Speaker {seg.speaker_label}: {seg.text}" for seg in segments
        ])

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a meticulous chief of staff and conversation intelligence assistant. "
                    "LANGUAGE INSTRUCTION: Generate the complete Minutes of Meeting (MOM) in clean, professional English or natural Hindi+English. "
                    "If the conversation is in English, respond in English. "
                    "If the conversation is in Hindi or mixed, respond in natural Hindi+English. "
                    "Keep all technical, business, and product terms in standard English (e.g., 'model', 'transcription', 'summary', 'deployment', 'testing', 'implementation'). "
                    "Never use artificial or broken phonetic transliterations. "
                    "Copy source_quote for every action item and context_quote for every decision verbatim. "
                    "Only include decisions and commitments supported by those quotes. "
                    "Leave unstated assignees and deadlines null."
                )
            },
            {
                "role": "user",
                "content": f"Generate structured meeting minutes (MOM) from this transcript:\n\n{transcript_text}"
            }
        ]

        result = await self.llm_client.generate_structured(messages=messages, response_model=MOMResult)
        elapsed = time.time() - start_time
        logger.info("mom_processed", session_id=session_id, elapsed=elapsed)
        return result
