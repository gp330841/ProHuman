"""
Database model for tracking uploaded audio chunks.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from .session import Session

class AudioChunk(Base, TimestampMixin):
    """
    Records an individual uploaded chunk of audio data.
    
    References the object storage location (e.g., S3 key) and ensures
    consistency using checksums and sequence indices.
    """
    __tablename__ = "audio_chunks"
    __table_args__ = (
        UniqueConstraint("session_id", "chunk_index", name="uq_chunk_session_index"),
        UniqueConstraint("session_id", "checksum", name="uq_chunk_session_checksum"),
    )

    id: Mapped[uuid_pk]
    session_id: Mapped[UUID] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int]
    s3_key: Mapped[str] = mapped_column(String(512))
    size_bytes: Mapped[int]
    duration_ms: Mapped[int | None]
    checksum: Mapped[str] = mapped_column(String(64))

    session: Mapped["Session"] = relationship(back_populates="audio_chunks")
