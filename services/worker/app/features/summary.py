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
            f"Speaker {seg.speaker_label}: {seg.text}" for seg in segments
        ])

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert meeting summarizer. "
                    "LANGUAGE INSTRUCTION: Generate the title, executive summary, and key topics in clean English or natural Hindi+English. "
                    "If the conversation is in English, respond in English. "
                    "If the conversation is in Hindi or mixed, respond in natural Hindi+English (Hinglish written in Latin/Roman script). "
                    "Keep all technical, business, and product terms in standard English. "
                    "If the speaker suggests a specific title for the meeting (e.g. 'iska title rakhna...'), adopt that title."
                )
            },
            {
                "role": "user",
                "content": f"Please summarize this transcript:\n\n{transcript_text}"
            }
        ]

        try:
            result = await self.llm_client.generate_structured(
                messages=messages,
                response_model=SummaryResult
            )
            elapsed = time.time() - start_time
            logger.info("summary_processed", session_id=session_id, elapsed=elapsed)
            return result
        except Exception as e:
            logger.warning("summary_llm_failed_falling_back_to_extractive", error=str(e))
            from packages.contracts.hinglish import devanagari_to_hinglish
            full_text = " ".join([devanagari_to_hinglish(seg.text) for seg in segments if seg.text])
            title = "Meeting Summary"
            if segments and len(segments[0].text) > 5:
                title = " ".join(devanagari_to_hinglish(segments[0].text).split()[:6]).title()
            return SummaryResult(
                title=title,
                executive_summary=full_text[:400] if full_text else "Meeting conversation record ki gayi.",
                key_topics=["Charcha", "Action Items", "Updates"],
                participant_count=len(set(seg.speaker_label for seg in segments)) or 1
            )
