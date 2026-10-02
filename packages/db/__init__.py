"""
Database package providing models, repositories, and engine configuration.

Exports core base classes, engine setup, and all SQLAlchemy models.
"""
from __future__ import annotations

from .base import Base, TimestampMixin, uuid_pk
from .engine import create_db_engine, async_session_factory, get_db_session, get_db_context
from .models.session import SessionStatusEnum, Session
from .models.audio_chunk import AudioChunk
from .models.transcript import TranscriptSegment
from .models.feature_result import FeatureResultModel

__all__ = [
    "Base",
    "TimestampMixin",
    "uuid_pk",
    "create_db_engine",
    "async_session_factory",
    "get_db_session",
    "get_db_context",
    "SessionStatusEnum",
    "Session",
    "AudioChunk",
    "TranscriptSegment",
    "FeatureResultModel",
]
