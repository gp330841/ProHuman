"""Execute durable pipeline work and commit results with the job outcome."""

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.pool import NullPool

from app.celery_app import celery_app
from app.config import settings
from app.tasks.embedding import embed
from app.tasks.feature_pipeline import extract_features
from app.tasks.transcription import transcribe
from packages.db.engine import create_db_engine, get_db_context
from packages.db.models.pipeline_job import PipelineJob
from packages.db.models.session import Session, SessionStatusEnum
from packages.db.repositories.pipeline_repo import enqueue_stage, stage_statuses

logger = structlog.get_logger(__name__)
handlers = {"transcription": transcribe, "embedding": embed, "features": extract_features}


async def run_job(job_id: UUID) -> None:
    async with get_db_context() as db:
        session_id = await db.scalar(select(PipelineJob.session_id).where(PipelineJob.id == job_id))
        if not session_id:
            return
        session = await db.get(Session, session_id, with_for_update=True)
        if session is None:
            return
        job = await db.get(PipelineJob, job_id, with_for_update=True)
        if job is None or job.state != "dispatched":
            return
        job.attempts += 1
        try:
            async with db.begin_nested():
                await handlers[job.stage](db, session, **job.payload)
            job.state = "completed"
        except Exception:
            logger.exception("pipeline_stage_failed", session_id=str(session_id), stage=job.stage)
            job.state = "failed" if job.attempts > settings.max_retries else "queued"
            job.available_at = datetime.now(timezone.utc) + timedelta(seconds=min(300, 5 ** job.attempts))
            await db.refresh(session)

        await db.flush()
        states = await stage_statuses(db, session_id)
        if states.get("transcription") == "failed":
            session.status = SessionStatusEnum.FAILED
        elif states.get("features") == "completed" and states.get("embedding") == "completed":
            session.status = SessionStatusEnum.COMPLETED


async def _run_with_engine(operation, *args):
    engine = create_db_engine(settings.database_url, poolclass=NullPool)
    try:
        await operation(*args)
    finally:
        await engine.dispose()


@celery_app.task(name="app.tasks.execute_pipeline_job")
def execute_pipeline_job(job_id: str) -> None:
    asyncio.run(_run_with_engine(run_job, UUID(job_id)))


async def _accept_legacy_job(session_id: str, stage: str, **payload):
    async with get_db_context() as db:
        if await db.get(Session, UUID(session_id)):
            await enqueue_stage(db, UUID(session_id), stage, **payload)


@celery_app.task(name="app.tasks.transcription.transcribe_session")
def transcribe_session(session_id: str, s3_key: str) -> None:
    asyncio.run(_run_with_engine(_accept_legacy_job, session_id, "transcription"))


@celery_app.task(name="app.tasks.embedding.generate_embeddings")
def generate_embeddings(session_id: str) -> None:
    asyncio.run(_run_with_engine(_accept_legacy_job, session_id, "embedding"))


@celery_app.task(name="app.tasks.feature_pipeline.run_feature_pipeline")
def run_feature_pipeline(session_id: str, feature_names=None, force=False) -> None:
    async def enqueue():
        await _accept_legacy_job(session_id, "features", feature_names=feature_names, force=force)
    asyncio.run(_run_with_engine(enqueue))
