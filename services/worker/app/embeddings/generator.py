"""Module for generator.py."""
from __future__ import annotations

import structlog

from packages.db.engine import get_db_context
from packages.db.repositories.transcript_repo import TranscriptRepository
from app.llm.client import LLMClient

logger = structlog.get_logger(__name__)

class EmbeddingGenerator:
    """Class documentation."""
    def __init__(self, llm_client: LLMClient, batch_size: int = 32):
        """Method documentation."""
        self.llm_client = llm_client
        self.batch_size = batch_size

    async def generate_for_session(self, session_id: str) -> int:
        """Method documentation."""
        async with get_db_context() as db_session:
            repo = TranscriptRepository(db_session)
            
            segments = await repo.get_by_session(session_id)
            if not segments:
                logger.info("no_segments_found_for_embedding", session_id=session_id)
                return 0
            
            # Filter segments that don't have embeddings yet
            segments_to_update = [seg for seg in segments if seg.embedding is None]
            if not segments_to_update:
                logger.info("all_segments_already_embedded", session_id=session_id)
                return 0

            texts = [seg.text for seg in segments_to_update]
            embeddings = await self.llm_client.generate_embeddings(texts)
            
            for seg, emb in zip(segments_to_update, embeddings):
                seg.embedding = emb
                # if search_vector logic needs to be updated here, update it
                # For PostgreSQL, typically it's handled via trigger, but can be set if needed
            
            # Since SQLAlchemy tracks changes to the objects if they are attached to the session,
            # committing the session will update them in the DB.
            await db_session.commit()
            
            count = len(segments_to_update)
            logger.info("embeddings_generated_and_saved", session_id=session_id, count=count)
            return count
