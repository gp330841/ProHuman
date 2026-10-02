"""
Feature extraction and analysis data contracts.

Defines schemas for AI-extracted insights like summaries, action items,
decisions, and sentiment analysis.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from pydantic import BaseModel, Field

class FeatureResult(BaseModel):
    """Generic wrapper for feature extraction results."""
    feature_name: str = Field(description="Name of the extracted feature")
    data: dict[str, Any] = Field(description="Feature-specific payload")
    processing_time_ms: int | None = Field(None, description="Time taken to process in ms")
    provider_model: str | None = Field(None, description="AI model used")
    version: int = Field(1, description="Schema version of this feature")

class SummaryResult(BaseModel):
    """Session summary details."""
    title: str = Field(description="Generated title for the session")
    executive_summary: str = Field(description="High-level summary of the session")
    key_topics: list[str] = Field(description="Main topics discussed")
    participant_count: int = Field(description="Number of distinct participants")

class ActionItem(BaseModel):
    """An action item extracted from the session."""
    description: str = Field(description="What needs to be done")
    assignee: str | None = Field(None, description="Who is responsible")
    deadline: date | None = Field(None, description="When it is due")
    priority: Literal["critical", "high", "medium", "low"] = Field(description="Urgency")
    confidence: float = Field(ge=0, le=1, default=1.0, description="Extraction confidence")
    source_quote: str | None = Field(None, description="Quote from transcript")
    status: Literal["pending", "in_progress", "completed", "cancelled"] = Field("pending", description="Current status")

class ActionItemsResult(BaseModel):
    """Collection of action items."""
    items: list[ActionItem] = Field(description="List of action items")

class Decision(BaseModel):
    """A decision made during the session."""
    description: str = Field(description="What was decided")
    made_by: str | None = Field(None, description="Who made the decision")
    context_quote: str | None = Field(None, description="Transcript quote for context")
    confidence: float = Field(ge=0, le=1, default=1.0, description="Extraction confidence")
    timestamp: float | None = Field(None, description="Time in session when decided")

class AgendaItem(BaseModel):
    """An item discussed from the agenda."""
    topic: str = Field(description="The topic discussed")
    summary: str = Field(description="Brief summary of the discussion")
    duration_seconds: float | None = Field(None, description="Time spent on topic")
    speakers_involved: list[str] = Field(description="Speakers who participated")

class FollowUp(BaseModel):
    """A follow-up task or meeting."""
    description: str = Field(description="What needs follow-up")
    responsible_party: str | None = Field(None, description="Who is responsible")
    due_context: str | None = Field(None, description="When or why it is due")

class MOMResult(BaseModel):
    """Minutes of Meeting (MOM) comprehensive result."""
    title: str = Field(description="Meeting title")
    date: datetime = Field(description="Meeting date")
    attendees: list[str] = Field(description="List of attendees")
    agenda_items: list[AgendaItem] = Field(description="Topics discussed")
    decisions: list[Decision] = Field(description="Decisions made")
    action_items: list[ActionItem] = Field(description="Action items assigned")
    follow_ups: list[FollowUp] = Field(description="Follow-up tasks")
    executive_summary: str = Field(description="High-level summary")

class SentimentEntry(BaseModel):
    """Sentiment analysis for a specific speaker."""
    speaker_label: str = Field(description="Identifier for the speaker")
    sentiment: Literal["positive", "negative", "neutral", "mixed"] = Field(description="Overall sentiment")
    confidence: float = Field(ge=0, le=1, description="Analysis confidence")
    notable_moments: list[str] = Field(default_factory=list, description="Key transcript quotes")

class SentimentResult(BaseModel):
    """Overall session sentiment result."""
    overall_sentiment: str = Field(description="General sentiment of the session")
    speaker_sentiments: list[SentimentEntry] = Field(description="Per-speaker sentiment details")
    sentiment_trend: list[dict[str, Any]] = Field(default_factory=list, description="Trend over time")
