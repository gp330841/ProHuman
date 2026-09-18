from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis
import structlog

logger = structlog.get_logger(__name__)

class TaskDispatcher:
    """Dispatches tasks via Redis Streams."""
    
    def __init__(self, redis_client: Redis) -> None:
        self.redis = redis_client

    async def _check_idempotency(self, stream: str, session_id: str) -> bool:
        """Check if task was already dispatched."""
        key = f"idempotency:dispatch:{stream}:{session_id}"
        is_set = await self.redis.setnx(key, "1")
        if is_set:
            await self.redis.expire(key, 3600)
        return bool(is_set)

    async def dispatch_transcription(self, session_id: str, s3_key: str) -> None:
        """Dispatch transcription task."""
        stream = "audio.ingest"
        if await self._check_idempotency(stream, session_id):
            await self.redis.xadd(stream, {"session_id": session_id, "s3_key": s3_key})
            await logger.ainfo("dispatched_transcription", session_id=session_id)

    async def dispatch_embedding(self, session_id: str) -> None:
        """Dispatch embedding task."""
        stream = "embed.generate"
        if await self._check_idempotency(stream, session_id):
            await self.redis.xadd(stream, {"session_id": session_id})
            await logger.ainfo("dispatched_embedding", session_id=session_id)

    async def dispatch_feature_pipeline(self, session_id: str, features: list[str] | None = None) -> None:
        """Dispatch feature extraction task."""
        stream = "features.extract"
        if await self._check_idempotency(stream, session_id):
            await self.redis.xadd(stream, {
                "session_id": session_id, 
                "features": json.dumps(features or [])
            })
            await logger.ainfo("dispatched_feature_pipeline", session_id=session_id)

__all__ = ["TaskDispatcher"]
