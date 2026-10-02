"""
Repository for managing transcript segments.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from .base import BaseRepository
from ..models.transcript import TranscriptSegment

class TranscriptRepository(BaseRepository[TranscriptSegment]):
    """Repository for querying and managing transcript segments, including vector search."""
    def __init__(self, session: AsyncSession):
        super().__init__(session, TranscriptSegment)

    async def get_by_session(self, session_id: UUID, order_by_index: bool = True) -> list[TranscriptSegment]:
        """
        Get all transcript segments for a session.
        
        Args:
            session_id: The session UUID.
            order_by_index: Whether to order by segment index.
        """
        stmt = select(TranscriptSegment).filter_by(session_id=session_id)
        if order_by_index:
            stmt = stmt.order_by(TranscriptSegment.segment_index)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def bulk_create(self, segments: list[dict]) -> list[TranscriptSegment]:
        """
        Create multiple transcript segments in one operation.
        
        Args:
            segments: List of dictionaries containing segment data.
        """
        instances = [TranscriptSegment(**segment) for segment in segments]
        self.session.add_all(instances)
        await self.session.flush()
        return instances

    async def hybrid_search(
        self,
        query_text: str,
        query_embedding: list[float],
        limit: int = 10,
        offset: int = 0,
        session_ids: list[UUID] | None = None,
        time_range_start: datetime | None = None,
        time_range_end: datetime | None = None,
        search_mode: str = "HYBRID",
        rrf_k: int = 60
    ) -> list[dict]:
        """
        Perform a hybrid semantic and lexical search over transcript segments.
        Uses Reciprocal Rank Fusion (RRF) to combine scores.
        """
        # Implementation of full RRF SQL query
        raw_sql = """
        WITH vector_search AS (
            SELECT
                id,
                1.0 / (:rrf_k + ROW_NUMBER() OVER (ORDER BY embedding <=> CAST(:query_embedding AS vector))) as vector_score,
                ROW_NUMBER() OVER (ORDER BY embedding <=> CAST(:query_embedding AS vector)) as vector_rank
            FROM transcript_segments
            WHERE embedding IS NOT NULL
              AND :search_mode != 'LEXICAL'
              AND (:session_ids_len = 0 OR session_id = ANY(:session_ids))
              AND (:time_start IS NULL OR created_at >= :time_start)
              AND (:time_end IS NULL OR created_at <= :time_end)
            ORDER BY embedding <=> CAST(:query_embedding AS vector)
            LIMIT :sub_limit
        ),
        text_search AS (
            SELECT
                id,
                1.0 / (:rrf_k + ROW_NUMBER() OVER (ORDER BY ts_rank_cd(search_vector, websearch_to_tsquery('english', :query_text)) DESC)) as text_score,
                ROW_NUMBER() OVER (ORDER BY ts_rank_cd(search_vector, websearch_to_tsquery('english', :query_text)) DESC) as text_rank
            FROM transcript_segments
            WHERE :search_mode != 'SEMANTIC'
              AND search_vector @@ websearch_to_tsquery('english', :query_text)
              AND (:session_ids_len = 0 OR session_id = ANY(:session_ids))
              AND (:time_start IS NULL OR created_at >= :time_start)
              AND (:time_end IS NULL OR created_at <= :time_end)
            ORDER BY ts_rank_cd(search_vector, websearch_to_tsquery('english', :query_text)) DESC
            LIMIT :sub_limit
        )
        SELECT
            COALESCE(v.id, t.id) as segment_id,
            COALESCE(v.vector_score, 0.0) + COALESCE(t.text_score, 0.0) as rrf_score,
            v.vector_rank,
            t.text_rank,
            ts.session_id,
            ts.speaker_label,
            ts.text,
            ts.start_time,
            ts.end_time,
            ts.created_at
        FROM vector_search v
        FULL OUTER JOIN text_search t ON v.id = t.id
        JOIN transcript_segments ts ON ts.id = COALESCE(v.id, t.id)
        ORDER BY rrf_score DESC
        LIMIT :limit OFFSET :offset
        """
        
        session_ids_arr = session_ids or []
        
        params = {
            "query_text": query_text,
            "query_embedding": str(query_embedding),
            "search_mode": search_mode,
            "limit": limit,
            "offset": offset,
            "rrf_k": rrf_k,
            "session_ids": session_ids_arr,
            "session_ids_len": len(session_ids_arr),
            "time_start": time_range_start,
            "time_end": time_range_end,
            "sub_limit": max(limit * 2, 100),
        }
        
        result = await self.session.execute(text(raw_sql), params)
        rows = result.mappings().all()
        return [dict(row) for row in rows]

    async def update_embeddings(self, segment_id: UUID, embedding: list[float]) -> None:
        """
        Update the vector embedding for a given transcript segment.
        """
        await self.update(segment_id, embedding=embedding)
