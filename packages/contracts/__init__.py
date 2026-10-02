"""
Shared data contracts and Pydantic models for the ProHuman platform.

This package exports all domain models used for inter-service communication
and data serialization/deserialization.
"""
from __future__ import annotations

from .audio import (
    AudioFormat,
    AudioChunkMeta,
    AudioSessionConfig,
    MAX_CHUNK_SIZE_BYTES,
    ALLOWED_SAMPLE_RATES,
    AUDIO_MAGIC_BYTES,
)
from .sessions import (
    SessionStatus,
    SessionCreate,
    SessionResponse,
    SessionDetail,
    SessionListResponse,
)
from .transcription import (
    WordTimestamp,
    TranscriptSegment,
    TranscriptionResult,
)
from .features import (
    FeatureResult,
    SummaryResult,
    ActionItem,
    ActionItemsResult,
    Decision,
    AgendaItem,
    MOMResult,
    FollowUp,
    SentimentEntry,
    SentimentResult,
)
from .search import (
    SearchMode,
    SearchRequest,
    SearchResultItem,
    SearchResponse,
)

__all__ = [
    "AudioFormat",
    "AudioChunkMeta",
    "AudioSessionConfig",
    "MAX_CHUNK_SIZE_BYTES",
    "ALLOWED_SAMPLE_RATES",
    "AUDIO_MAGIC_BYTES",
    "SessionStatus",
    "SessionCreate",
    "SessionResponse",
    "SessionDetail",
    "SessionListResponse",
    "WordTimestamp",
    "TranscriptSegment",
    "TranscriptionResult",
    "FeatureResult",
    "SummaryResult",
    "ActionItem",
    "ActionItemsResult",
    "Decision",
    "AgendaItem",
    "MOMResult",
    "FollowUp",
    "SentimentEntry",
    "SentimentResult",
    "SearchMode",
    "SearchRequest",
    "SearchResultItem",
    "SearchResponse",
]
