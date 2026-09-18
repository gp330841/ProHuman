from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID
from pydantic import BaseModel, Field, model_validator

class SearchMode(str, Enum):
    HYBRID = "HYBRID"
    SEMANTIC = "SEMANTIC"
    LEXICAL = "LEXICAL"

class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    search_mode: SearchMode = SearchMode.HYBRID
    time_range_start: datetime | None = None
    time_range_end: datetime | None = None
    participant_names: list[str] | None = None
    topic_tags: list[str] | None = None
    session_ids: list[UUID] | None = None
    limit: int = Field(default=10, ge=1, le=50)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_time_range(self) -> SearchRequest:
        if self.time_range_start and self.time_range_end:
            if self.time_range_end <= self.time_range_start:
                raise ValueError("time_range_end must be after time_range_start")
        return self

class SearchResultItem(BaseModel):
    segment_id: UUID
    session_id: UUID
    session_title: str | None = None
    speaker_label: str
    speaker_name: str | None = None
    text: str
    start_time: float
    end_time: float
    rrf_score: float
    vector_rank: int | None = None
    text_rank: int | None = None
    session_date: datetime

class SearchResponse(BaseModel):
    results: list[SearchResultItem]
    total_count: int
    query_embedding_model: str
    search_mode_used: SearchMode
