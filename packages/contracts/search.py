"""
Search request and response data contracts.

Defines schemas for vector, lexical, and hybrid search queries and results.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID
from pydantic import BaseModel, Field, model_validator

class SearchMode(str, Enum):
    """The search algorithm mode to use."""
    HYBRID = "HYBRID"
    SEMANTIC = "SEMANTIC"
    LEXICAL = "LEXICAL"

class SearchRequest(BaseModel):
    """A request to search through transcripts and sessions."""
    query: str = Field(min_length=2, max_length=500, description="The search query text")
    search_mode: SearchMode = Field(default=SearchMode.HYBRID, description="Search algorithm to use")
    time_range_start: datetime | None = Field(default=None, description="Start of the session time range filter")
    time_range_end: datetime | None = Field(default=None, description="End of the session time range filter")
    participant_names: list[str] | None = Field(default=None, description="Filter by participant names")
    topic_tags: list[str] | None = Field(default=None, description="Filter by assigned topic tags")
    session_ids: list[UUID] | None = Field(default=None, description="Restrict search to specific sessions")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of results to return")
    offset: int = Field(default=0, ge=0, description="Pagination offset")

    @model_validator(mode="after")
    def validate_time_range(self) -> SearchRequest:
        if self.time_range_start and self.time_range_end:
            if self.time_range_end <= self.time_range_start:
                raise ValueError("time_range_end must be after time_range_start")
        return self

class SearchResultItem(BaseModel):
    """An individual search result segment."""
    segment_id: UUID = Field(description="Unique ID of the matched transcript segment")
    session_id: UUID = Field(description="ID of the session containing the segment")
    session_title: str | None = Field(default=None, description="Title of the session")
    speaker_label: str = Field(description="Label of the speaker")
    speaker_name: str | None = Field(default=None, description="Name of the speaker")
    text: str = Field(description="Transcript text of the segment")
    start_time: float = Field(description="Start time of the segment in the session")
    end_time: float = Field(description="End time of the segment in the session")
    rrf_score: float = Field(description="Reciprocal Rank Fusion score (for hybrid search)")
    vector_rank: int | None = Field(default=None, description="Rank from semantic search")
    text_rank: int | None = Field(default=None, description="Rank from lexical search")
    session_date: datetime = Field(description="Date and time the session occurred")

class SearchResponse(BaseModel):
    """The response containing search results and metadata."""
    results: list[SearchResultItem] = Field(description="List of matching segments")
    total_count: int = Field(description="Total number of matches available")
    query_embedding_model: str = Field(description="The model used to embed the query")
    search_mode_used: SearchMode = Field(description="The actual search mode executed")
