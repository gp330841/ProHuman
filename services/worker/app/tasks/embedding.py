from __future__ import annotations

import asyncio
import structlog
from asgiref.sync import async_to_sync

from app.celery_app import celery_app
from app.embeddings.generator import EmbeddingGenerator
from app.llm.client import LLMClient
from packages.db.engine import get_db_context
from packages.db.repositories.session_repo import SessionRepository
from packages.db.models.session import SessionStatusEnum

logger = structlog.get_logger(__name__)

async def _generate_embeddings_async(session_id: str) -> None:
    generator = EmbeddingGenerator(llm_client=LLMClient())
    count = await generator.generate_for_session(session_id)
    
    if count > 0:
        async with get_db_context() as db:
            session_repo = SessionRepository(db)
            await session_repo.update_status(session_id, SessionStatusEnum.INDEXED)
            await db.commit()

@celery_app.task(bind=True, max_retries=3, acks_late=True, queue='embedding')
def generate_embeddings(self, session_id: str) -> None:
    try:
        async_to_sync(_generate_embeddings_async)(session_id)
    except Exception as exc:
        self.retry(exc=exc, countdown=2 ** self.request.retries)
