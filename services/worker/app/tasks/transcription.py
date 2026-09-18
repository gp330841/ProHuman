from __future__ import annotations

import asyncio
import structlog
from asgiref.sync import async_to_sync

from app.celery_app import celery_app
from app.config import settings
from app.stt.deepgram_adapter import DeepgramAdapter
from app.stt.whisperx_adapter import WhisperXAdapter
from packages.db.engine import get_db_context
from packages.db.repositories.session_repo import SessionRepository
from packages.db.repositories.transcript_repo import TranscriptRepository
from packages.db.models.session import SessionStatusEnum
from packages.db.models.transcript import TranscriptSegment as TranscriptSegmentModel

logger = structlog.get_logger(__name__)

async def _transcribe_session_async(session_id: str, s3_key: str) -> None:
    async with get_db_context() as db:
        session_repo = SessionRepository(db)
        transcript_repo = TranscriptRepository(db)
        
        # Idempotency check
        existing = await transcript_repo.get_by_session(session_id)
        if existing:
            logger.info("session_already_transcribed", session_id=session_id)
            return
            
        await session_repo.update_status(session_id, SessionStatusEnum.TRANSCRIBING)
        await db.commit()

        try:
            # Get presigned URL via aiobotocore / boto3 or use audio_url directly
            import aioboto3
            session = aioboto3.Session()
            async with session.client('s3',
                                      endpoint_url=settings.s3_endpoint_url,
                                      aws_access_key_id=settings.s3_access_key,
                                      aws_secret_access_key=settings.s3_secret_key) as s3_client:
                audio_url = await s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': settings.s3_bucket_name, 'Key': s3_key},
                    ExpiresIn=3600
                )
            
            adapter = DeepgramAdapter(api_key=settings.deepgram_api_key)
            result = await adapter.transcribe(audio_url)
            
            # Bulk insert segments with matching database schema
            models = [
                TranscriptSegmentModel(
                    session_id=session_id,
                    segment_index=idx,
                    speaker_label=seg.speaker_label or f"speaker_{seg.speaker_id}",
                    text=seg.text,
                    start_time=seg.start_time,
                    end_time=seg.end_time,
                    confidence=seg.confidence,
                    word_timestamps=[w.model_dump() for w in seg.words] if hasattr(seg, 'words') and seg.words else []
                )
                for idx, seg in enumerate(result.segments)
            ]
            
            for m in models:
                db.add(m)
                
            await session_repo.update_status(session_id, SessionStatusEnum.TRANSCRIBED)
            await db.commit()
            
            # Dispatch further tasks
            from app.tasks.embedding import generate_embeddings
            from app.tasks.feature_pipeline import run_feature_pipeline
            
            generate_embeddings.delay(session_id)
            run_feature_pipeline.delay(session_id)
            
        except Exception as e:
            logger.error("transcription_failed", session_id=session_id, error=str(e))
            await session_repo.update_status(session_id, SessionStatusEnum.FAILED)
            await db.commit()
            raise

@celery_app.task(bind=True, max_retries=3, acks_late=True, queue='transcription')
def transcribe_session(self, session_id: str, s3_key: str) -> None:
    try:
        async_to_sync(_transcribe_session_async)(session_id, s3_key)
    except Exception as exc:
        self.retry(exc=exc, countdown=2 ** self.request.retries)
