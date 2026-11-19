"""Run the actual Celery worker with deterministic providers for release verification."""

from datetime import datetime, timezone

from app.celery_app import celery_app
from app.features.registry import FeatureRegistry
from app.llm.client import LLMClient
from app.stt.base import STTResult
from app.stt.deepgram_adapter import DeepgramAdapter
from packages.contracts.features import ActionItem, MOMResult
from packages.contracts.transcription import TranscriptSegment

QUOTE = "Mira will send the budget."
embedding_attempts = 0


async def transcribe(self, audio, config):
    if not isinstance(audio, bytes) or len(audio) < 100:
        raise ValueError("Expected real audio from object storage")
    return STTResult(
        duration_seconds=1.5,
        speaker_count=1,
        segments=[TranscriptSegment(
            segment_index=0, speaker_label="speaker_0", text=QUOTE, start_time=0.25, end_time=0.75,
        )],
    )


async def embed(self, texts):
    global embedding_attempts
    embedding_attempts += 1
    if embedding_attempts == 1:
        raise RuntimeError("Simulated transient embedding failure")
    return [[1.0] + [0.0] * 1535 for _ in texts]


class TestMomProvider:
    name = "mom"

    def validate_context(self, context):
        return bool(context["transcript"])

    async def process(self, session_id, context):
        return MOMResult(
            title="Budget review",
            date=datetime.now(timezone.utc),
            attendees=["Mira"],
            agenda_items=[],
            decisions=[],
            action_items=[ActionItem(
                description="Send the budget", assignee="Mira", source_quote=QUOTE, priority="medium",
            )],
            follow_ups=[],
            executive_summary="The team discussed the budget.",
        )


if __name__ == "__main__":
    DeepgramAdapter.transcribe = transcribe
    LLMClient.generate_embeddings = embed
    FeatureRegistry.discover = classmethod(lambda cls, package: None)
    FeatureRegistry.register(TestMomProvider)
    celery_app.worker_main(["worker", "--pool=solo", "--queues=transcription,embedding,features", "--loglevel=INFO"])
