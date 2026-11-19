"""Embed transcript segments in the same transaction as stage completion."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.embeddings.generator import EmbeddingGenerator
from app.llm.client import LLMClient
from packages.db.models.session import Session


async def embed(db: AsyncSession, session: Session) -> None:
    await EmbeddingGenerator(LLMClient()).generate_for_session(db, session.id)
