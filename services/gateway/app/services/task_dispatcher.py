"""Module for task_dispatcher.py."""
from __future__ import annotations

from celery import Celery

from redis.asyncio import Redis
import structlog

logger = structlog.get_logger(__name__)

class TaskDispatcher:
    """Submit worker tasks to the Redis-backed Celery broker."""
    
    def __init__(self, redis_client: Redis, broker_url: str) -> None:
        """Method documentation."""
        self.redis = redis_client
        self.celery = Celery("gateway", broker=broker_url)

    async def _check_idempotency(self, task_name: str, task_key: str) -> bool:
        """Check if task was already dispatched."""
        key = f"idempotency:dispatch:{task_name}:{task_key}"
        is_set = await self.redis.setnx(key, "1")
        if is_set:
            await self.redis.expire(key, 3600)
        return bool(is_set)

    async def dispatch_transcription(self, session_id: str, s3_key: str) -> None:
        """Dispatch transcription task."""
        task_name = "app.tasks.transcription.transcribe_session"
        if await self._check_idempotency(task_name, f"{session_id}:{s3_key}"):
            try:
                self.celery.send_task(task_name, args=[session_id, s3_key], queue="transcription")
            except Exception:
                await self.redis.delete(f"idempotency:dispatch:{task_name}:{session_id}:{s3_key}")
                raise
            await logger.ainfo("dispatched_transcription", session_id=session_id)

    async def dispatch_embedding(self, session_id: str) -> None:
        """Dispatch embedding task."""
        task_name = "app.tasks.embedding.generate_embeddings"
        if await self._check_idempotency(task_name, session_id):
            self.celery.send_task(task_name, args=[session_id], queue="embedding")
            await logger.ainfo("dispatched_embedding", session_id=session_id)

    async def dispatch_feature_pipeline(
        self,
        session_id: str,
        features: list[str] | None = None,
        force: bool = False,
    ) -> None:
        """Dispatch feature extraction task."""
        task_name = "app.tasks.feature_pipeline.run_feature_pipeline"
        task_key = f"{session_id}:{','.join(features or [])}:{force}"
        if await self._check_idempotency(task_name, task_key):
            try:
                self.celery.send_task(
                    task_name,
                    args=[session_id, features or None, force],
                    queue="features",
                )
            except Exception:
                await self.redis.delete(f"idempotency:dispatch:{task_name}:{task_key}")
                raise
            await logger.ainfo("dispatched_feature_pipeline", session_id=session_id)

__all__ = ["TaskDispatcher"]
