"""Generate and validate embeddings before writing them to the transcript."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import LLMClient
from packages.db.models.transcript import EMBEDDING_DIM
from packages.db.repositories.transcript_repo import TranscriptRepository


class EmbeddingGenerator:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    async def generate_for_session(self, db: AsyncSession, session_id: UUID) -> int:
        segments = await TranscriptRepository(db).get_by_session(session_id)
        pending = [segment for segment in segments if segment.embedding is None]
        if not pending:
            return 0
        vectors = await self.llm_client.generate_embeddings([segment.text for segment in pending])
        if len(vectors) != len(pending) or any(
            len(vector) != EMBEDDING_DIM or not any(vector) for vector in vectors
        ):
            raise ValueError("Embedding provider returned invalid results")
        for segment, vector in zip(pending, vectors, strict=True):
            segment.embedding = vector
        return len(pending)
