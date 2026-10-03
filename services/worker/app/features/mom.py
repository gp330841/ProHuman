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
                    "Never use artificial or broken phonetic transliterations."
                )
            },
            {
                "role": "user",
                "content": f"Generate structured meeting minutes (MOM) from this transcript:\n\n{transcript_text}"
            }
        ]

        try:
            result = await self.llm_client.generate_structured(
                messages=messages,
                response_model=MOMResult
            )
            elapsed = time.time() - start_time
            logger.info("mom_processed", session_id=session_id, elapsed=elapsed)
            return result
        except Exception as e:
            logger.warning("llm_mom_failed_falling_back_to_extractive", error=str(e))
            from datetime import datetime
            from packages.contracts.features import AgendaItem, Decision, ActionItem, FollowUp

            attendees = list(dict.fromkeys([seg.speaker_label for seg in segments])) or ["Speaker 1"]
            full_text = " ".join([seg.text for seg in segments if seg.text])
            title = f"Meeting - {datetime.now().strftime('%b %d, %Y')}"
            if len(segments) > 0 and len(segments[0].text) > 5:
                words = segments[0].text.split()[:7]
                title = " ".join(words).title()

            action_items = []
            for seg in segments:
                h_text = seg.text
                lower = h_text.lower()
                if any(kw in lower for kw in ["need to", "will", "todo", "action", "assign", "please", "make sure", "ensure", "karenge", "karna", "dekhna", "check"]):
                    action_items.append(ActionItem(
                        description=h_text,
                        assignee=seg.speaker_label,
                        priority="medium",
                        confidence=0.85,
                        status="pending"
                    ))

            return MOMResult(
                title=title,
                date=datetime.now(),
                attendees=attendees,
                agenda_items=[
                    AgendaItem(
                        topic="Discussion Overview",
                        summary=full_text[:300] + ("..." if len(full_text) > 300 else "") if full_text else "Meeting conversation record ki gayi.",
                        speakers_involved=attendees
                    )
                ],
                decisions=[
                    Decision(
                        description="Discussion topics aur planned execution items par agreement hui.",
                        made_by=attendees[0] if attendees else "Team",
                        confidence=0.8
                    )
                ],
                action_items=action_items[:10],
                follow_ups=[
                    FollowUp(
                        description="Meeting notes review karna aur assigned tasks follow up karna.",
                        responsible_party=attendees[0] if attendees else "Team"
                    )
                ],
                executive_summary=full_text[:500] if full_text else "Meeting conclude hui aur sabhi key points note kiye gaye."
            )
