from __future__ import annotations

import enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.contracts.sessions import SessionStatus
from ..base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from .audio_chunk import AudioChunk
    from .transcript import TranscriptSegment
    from .feature_result import FeatureResultModel

class SessionStatusEnum(str, enum.Enum):
    CREATED = SessionStatus.CREATED.value
    RECORDING = SessionStatus.RECORDING.value
    PROCESSING = SessionStatus.PROCESSING.value
    TRANSCRIBING = SessionStatus.TRANSCRIBING.value
    TRANSCRIBED = SessionStatus.TRANSCRIBED.value
    INDEXING = SessionStatus.INDEXING.value
    INDEXED = SessionStatus.INDEXED.value
    EXTRACTING = SessionStatus.EXTRACTING.value
    COMPLETED = SessionStatus.COMPLETED.value
    FAILED = SessionStatus.FAILED.value

class Session(Base, TimestampMixin):
    __tablename__ = "sessions"

    id: Mapped[uuid_pk]
    device_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[SessionStatusEnum] = mapped_column(default=SessionStatusEnum.CREATED, index=True)
    duration_seconds: Mapped[float | None]
    audio_format: Mapped[str | None] = mapped_column(String(50))
    sample_rate: Mapped[int | None]
    s3_key: Mapped[str | None] = mapped_column(String(512))
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, server_default="{}")

    audio_chunks: Mapped[list["AudioChunk"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    transcript_segments: Mapped[list["TranscriptSegment"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    feature_results: Mapped[list["FeatureResultModel"]] = relationship(back_populates="session", cascade="all, delete-orphan")
