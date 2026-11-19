"""Transcribe a finalized object and schedule dependent stages."""

import aiobotocore.session
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.stt.deepgram_adapter import DeepgramAdapter
from packages.db.models.session import Session, SessionStatusEnum
from packages.db.repositories.pipeline_repo import enqueue_stage
from packages.db.repositories.transcript_repo import TranscriptRepository


async def transcribe(db: AsyncSession, session: Session) -> None:
    repo = TranscriptRepository(db)
    if not await repo.get_by_session(session.id):
        if not settings.deepgram_api_key:
            raise RuntimeError("Speech provider not configured")
        if not session.s3_key:
            raise RuntimeError("Finalized audio missing")
        async with aiobotocore.session.get_session().create_client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
        ) as client:
            obj = await client.get_object(Bucket=settings.s3_bucket_name, Key=session.s3_key)
            async with obj["Body"] as body:
                audio = await body.read()
        result = await DeepgramAdapter(settings.deepgram_api_key).transcribe(
            audio, {"language": (session.metadata_ or {}).get("language", "auto")}
        )
        if not result.segments:
            raise ValueError("No speech was detected")
        await repo.bulk_create([
            {
                "session_id": session.id,
                "segment_index": index,
                "speaker_label": segment.speaker_label,
                "text": segment.text,
                "start_time": segment.start_time,
                "end_time": segment.end_time,
                "confidence": segment.confidence,
                "word_timestamps": [word.model_dump() for word in segment.words or []],
            }
            for index, segment in enumerate(result.segments)
        ])
        session.duration_seconds = result.duration_seconds

    session.status = SessionStatusEnum.TRANSCRIBED
    await enqueue_stage(db, session.id, "embedding")
    await enqueue_stage(db, session.id, "features")
