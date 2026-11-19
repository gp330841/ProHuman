"""Stable transcript references resolved from stored segments."""

from uuid import UUID

from pydantic import BaseModel


class TranscriptEvidence(BaseModel):
    session_id: UUID
    segment_id: UUID
    start_time: float
    end_time: float
