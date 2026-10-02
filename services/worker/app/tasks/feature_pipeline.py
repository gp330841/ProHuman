"""Module for feature_pipeline.py."""
from __future__ import annotations

import asyncio
import structlog
from asgiref.sync import async_to_sync

from app.celery_app import celery_app
from app.features.registry import FeatureRegistry
from packages.db.engine import get_db_context
from packages.db.repositories.session_repo import SessionRepository
from packages.db.repositories.transcript_repo import TranscriptRepository
from packages.db.repositories.feature_repo import FeatureRepository
from packages.db.models.session import SessionStatusEnum
from packages.db.models.feature_result import FeatureResultModel
from packages.contracts.transcription import TranscriptSegment

logger = structlog.get_logger(__name__)

async def _run_feature_pipeline_async(
    session_id: str,
    feature_names: list[str] | None = None,
    force: bool = False,
) -> None:
    async with get_db_context() as db:
        session_repo = SessionRepository(db)
        transcript_repo = TranscriptRepository(db)
        feature_repo = FeatureRepository(db)
        
        await session_repo.update_status(session_id, SessionStatusEnum.EXTRACTING)
        await db.commit()

        # Load transcript context
        segments = await transcript_repo.get_by_session(session_id)
        # Convert ORM to Pydantic objects expected by features
        transcript_data = {
            'transcript': [
                TranscriptSegment(
                    segment_index=s.segment_index,
                    speaker_label=s.speaker_label,
                    text=s.text,
                    start_time=s.start_time,
                    end_time=s.end_time,
                    confidence=s.confidence,
                    words=s.word_timestamps or []
                ) for s in segments
            ]
        }

        FeatureRegistry.discover('app.features')
        all_providers = FeatureRegistry.get_all()
        
        target_features = feature_names or list(all_providers.keys())
        
        for name in target_features:
            if name not in all_providers:
                logger.warning("unknown_feature_provider", name=name)
                continue
                
            provider_cls = all_providers[name]
            provider = provider_cls()
            
            if not provider.validate_context(transcript_data):
                logger.error("invalid_context_for_feature", feature=name)
                continue

            # Idempotency
            existing = await feature_repo.get_by_session_and_name(session_id, name)
            if existing and not force:
                logger.info("feature_already_extracted", feature=name, session_id=session_id)
                continue

            try:
                result = await provider.process(session_id, transcript_data)
                
                # Use standard Pydantic dumping if needed or if result is BaseModel
                data_dict = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
                
                next_version = await feature_repo.get_latest_version(session_id, name) + 1
                feature_model = FeatureResultModel(
                    session_id=session_id,
                    feature_name=name,
                    version=next_version,
                    data=data_dict
                )
                db.add(feature_model)
                await db.commit()
                logger.info("feature_extraction_success", feature=name, session_id=session_id)
            except Exception as e:
                logger.error("feature_extraction_failed", feature=name, session_id=session_id, error=str(e))
                # Continue with other features even if one fails

        await session_repo.update_status(session_id, SessionStatusEnum.COMPLETED)
        await db.commit()

@celery_app.task(bind=True, max_retries=3, acks_late=True, queue='features')
def run_feature_pipeline(
    self,
    session_id: str,
    feature_names: list[str] | None = None,
    force: bool = False,
) -> None:
    try:
        async_to_sync(_run_feature_pipeline_async)(session_id, feature_names, force)
    except Exception as exc:
        self.retry(exc=exc, countdown=2 ** self.request.retries)
