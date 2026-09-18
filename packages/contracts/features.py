from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from pydantic import BaseModel, Field

class FeatureResult(BaseModel):
    feature_name: str
    data: dict[str, Any]
    processing_time_ms: int | None = None
    provider_model: str | None = None
    version: int = 1

class SummaryResult(BaseModel):
    title: str
    executive_summary: str
    key_topics: list[str]
    participant_count: int

class ActionItem(BaseModel):
    description: str
    assignee: str | None = None
    deadline: date | None = None
    priority: Literal["critical", "high", "medium", "low"]
    confidence: float = Field(ge=0, le=1, default=1.0)
    source_quote: str | None = None
    status: Literal["pending", "in_progress", "completed", "cancelled"] = "pending"

class ActionItemsResult(BaseModel):
    items: list[ActionItem]

class Decision(BaseModel):
    description: str
    made_by: str | None = None
    context_quote: str | None = None
    confidence: float = Field(ge=0, le=1, default=1.0)
    timestamp: float | None = None

class AgendaItem(BaseModel):
    topic: str
    summary: str
    duration_seconds: float | None = None
    speakers_involved: list[str]

class FollowUp(BaseModel):
    description: str
    responsible_party: str | None = None
    due_context: str | None = None

class MOMResult(BaseModel):
    title: str
    date: datetime
    attendees: list[str]
    agenda_items: list[AgendaItem]
    decisions: list[Decision]
    action_items: list[ActionItem]
    follow_ups: list[FollowUp]
    executive_summary: str

class SentimentEntry(BaseModel):
    speaker_label: str
    sentiment: Literal["positive", "negative", "neutral", "mixed"]
    confidence: float = Field(ge=0, le=1)
    notable_moments: list[str] = Field(default_factory=list)

class SentimentResult(BaseModel):
    overall_sentiment: str
    speaker_sentiments: list[SentimentEntry]
    sentiment_trend: list[dict[str, Any]] = Field(default_factory=list)
