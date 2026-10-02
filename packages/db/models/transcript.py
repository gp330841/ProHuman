"""
Database model for transcript segments.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, Computed, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from ..base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from .session import Session

EMBEDDING_DIM = 1536

class TranscriptSegment(Base, TimestampMixin):
    """
    Stores an individual segment of transcribed audio.
    
    Includes text, speaker information, semantic embeddings for vector search,
    and tsvector columns for full-text search.
    """
    __tablename__ = "transcript_segments"
    __table_args__ = (
        CheckConstraint("end_time >= start_time", name="check_segment_time_validity"),
        Index("ix_segment_session_time", "session_id", "start_time"),
        Index("ix_segment_search_vector_gin", "search_vector", postgresql_using="gin"),
        Index(
            "ix_segment_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"}
        ),
    )

    id: Mapped[uuid_pk]
    session_id: Mapped[UUID] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    segment_index: Mapped[int]
    speaker_label: Mapped[str] = mapped_column(String(50))
    text: Mapped[str] = mapped_column(Text)
    start_time: Mapped[float] = mapped_column(index=True)
    end_time: Mapped[float]
    confidence: Mapped[float | None]
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english', coalesce(text, ''))", persisted=True)
    )
    word_timestamps: Mapped[list | None] = mapped_column(JSONB, server_default="[]")

    session: Mapped["Session"] = relationship(back_populates="transcript_segments")
