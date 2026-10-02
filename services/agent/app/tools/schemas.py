"""
agent/tools/schemas.py — Production Tool Catalog

All tool input/output schemas for the Conversation Intelligence Agent.
Conforms to OpenAI Function Calling and Anthropic Tool Use specifications.
"""

from __future__ import annotations

import enum
from datetime import datetime, date
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Shared Enums & Types
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SearchMode(str, enum.Enum):
    """Class documentation."""
    HYBRID = "hybrid"       # RRF over vector + full-text
    SEMANTIC = "semantic"   # pgvector cosine only
    LEXICAL = "lexical"     # tsvector BM25 only


class ActionItemStatus(str, enum.Enum):
    """Class documentation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ActionItemPriority(str, enum.Enum):
    """Class documentation."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ExternalTarget(str, enum.Enum):
    """Class documentation."""
    SLACK = "slack"
    NOTION = "notion"
    LINEAR = "linear"
    WEBHOOK = "webhook"


class ApprovalStatus(str, enum.Enum):
    """Class documentation."""
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Tool 1: search_conversations
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SearchConversationsInput(BaseModel):
    """
    Hybrid search across all transcribed conversations.
    Combines semantic vector similarity and lexical full-text matching
    using Reciprocal Rank Fusion (RRF, k=60).
    """

    query: str = Field(
        ...,
        min_length=2,
        max_length=500,
        description=(
            "Natural language search query. Searches both semantic meaning "
            "(via embedding similarity) and exact keyword matches "
            "(via PostgreSQL full-text search)."
        ),
    )
    search_mode: SearchMode = Field(
        default=SearchMode.HYBRID,
        description="Search strategy: 'hybrid' (default, recommended), 'semantic', or 'lexical'.",
    )
    time_range_start: datetime | None = Field(
        default=None,
        description="Filter results to conversations after this ISO-8601 timestamp.",
    )
    time_range_end: datetime | None = Field(
        default=None,
        description="Filter results to conversations before this ISO-8601 timestamp.",
    )
    participant_names: list[str] | None = Field(
        default=None,
        max_length=10,
        description=(
            "Filter by speaker/participant names. Matches against Speaker.display_name "
            "using case-insensitive prefix matching."
        ),
    )
    topic_tags: list[str] | None = Field(
        default=None,
        max_length=10,
        description="Filter by topic tags extracted during feature analysis.",
    )
    session_ids: list[UUID] | None = Field(
        default=None,
        max_length=20,
        description="Restrict search to specific session IDs.",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of results to return (1–50).",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Pagination offset for result cursor.",
    )

    @field_validator("time_range_end")
    @classmethod
    def validate_time_range(cls, v: datetime | None, info) -> datetime | None:
        """Method documentation."""
        start = info.data.get("time_range_start")
        if v and start and v <= start:
            raise ValueError("time_range_end must be after time_range_start")
        return v


class SearchResultSegment(BaseModel):
    """Class documentation."""
    segment_id: UUID
    session_id: UUID
    session_title: str | None = None
    speaker_label: str
    speaker_name: str | None = None
    text: str
    start_time: float = Field(description="Segment start time in seconds")
    end_time: float = Field(description="Segment end time in seconds")
    rrf_score: float = Field(description="Reciprocal Rank Fusion score (higher = more relevant)")
    vector_rank: int | None = Field(default=None, description="Rank in semantic search (null if not in vector results)")
    text_rank: int | None = Field(default=None, description="Rank in lexical search (null if not in text results)")
    session_date: datetime | None = None


class SearchConversationsOutput(BaseModel):
    """Class documentation."""
    results: list[SearchResultSegment]
    total_count: int
    query_embedding_model: str = Field(default="text-embedding-3-small", description="Embedding model used for semantic component")
    search_mode_used: SearchMode = SearchMode.HYBRID


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Tool 2: fetch_conversation_context
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ContextWindowMode(str, enum.Enum):
    """Class documentation."""
    TIMESTAMP = "timestamp"       # Window around a specific time
    SEGMENT = "segment"           # Window around a specific segment
    SPEAKER_TURNS = "speaker_turns"  # N turns before/after


class FetchConversationContextInput(BaseModel):
    """
    Retrieve a windowed slice of a conversation transcript.
    Prevents context-window blowout by returning only the relevant
    surrounding context rather than the full transcript.
    """

    session_id: UUID = Field(
        ...,
        description="The conversation session to retrieve context from.",
    )
    mode: ContextWindowMode = Field(
        default=ContextWindowMode.TIMESTAMP,
        description="How to anchor the context window.",
    )
    anchor_timestamp: float | None = Field(
        default=None,
        ge=0.0,
        description=(
            "Center timestamp in seconds (required when mode='timestamp'). "
            "Returns segments within ±window_seconds of this point."
        ),
    )
    anchor_segment_id: UUID | None = Field(
        default=None,
        description="Center segment ID (required when mode='segment').",
    )
    speaker_filter: list[str] | None = Field(
        default=None,
        description="Only include segments from these speaker labels (e.g., ['speaker_0']).",
    )
    window_seconds: float = Field(
        default=120.0,
        ge=10.0,
        le=600.0,
        description="Half-width of the time window in seconds (default ±120s = 4 min total).",
    )
    window_turns: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of speaker turns before and after the anchor (mode='speaker_turns').",
    )
    include_word_timestamps: bool = Field(
        default=False,
        description="Include word-level timing data in the response (increases payload size).",
    )

    @field_validator("anchor_timestamp")
    @classmethod
    def require_timestamp_for_mode(cls, v, info):
        """Method documentation."""
        if info.data.get("mode") == ContextWindowMode.TIMESTAMP and v is None:
            raise ValueError("anchor_timestamp is required when mode='timestamp'")
        return v

    @field_validator("anchor_segment_id")
    @classmethod
    def require_segment_for_mode(cls, v, info):
        """Method documentation."""
        if info.data.get("mode") == ContextWindowMode.SEGMENT and v is None:
            raise ValueError("anchor_segment_id is required when mode='segment'")
        return v


class ContextSegment(BaseModel):
    """Class documentation."""
    segment_id: UUID
    segment_index: int
    speaker_label: str
    speaker_name: str | None = None
    text: str
    start_time: float
    end_time: float
    confidence: float | None = None
    word_timestamps: list[dict[str, Any]] | None = None


class FetchConversationContextOutput(BaseModel):
    """Class documentation."""
    session_id: UUID
    session_title: str | None = None
    session_date: datetime | None = None
    total_duration_seconds: float | None = None
    window_start_time: float
    window_end_time: float
    segments: list[ContextSegment]
    speakers_in_window: list[str]
    truncated: bool = Field(
        default=False,
        description="True if the window was capped to prevent exceeding token limits"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Tool 3: generate_mom_and_actions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class GenerateMOMInput(BaseModel):
    """
    Extract structured Minutes of Meeting (MOM), explicit decisions,
    agenda items, and typed action items from a conversation session.
    Uses LLM with Pydantic schema enforcement (via Instructor) for
    deterministic JSON output.
    """

    session_id: UUID = Field(
        ...,
        description="The conversation session to analyze.",
    )
    focus_topics: list[str] | None = Field(
        default=None,
        max_length=10,
        description=(
            "Optional topic hints to guide extraction. "
            "E.g., ['budget allocation', 'Q3 roadmap']. "
            "If omitted, all topics are extracted."
        ),
    )
    extract_action_items: bool = Field(
        default=True,
        description="Whether to extract assignee-tagged action items.",
    )
    extract_decisions: bool = Field(
        default=True,
        description="Whether to extract explicit decisions made during the meeting.",
    )
    extract_follow_ups: bool = Field(
        default=True,
        description="Whether to extract follow-up items and pending questions.",
    )
    force_regenerate: bool = Field(
        default=False,
        description=(
            "If True, regenerate even if MOM already exists for this session. "
            "Creates a new version (version N+1)."
        ),
    )


class ExtractedDecision(BaseModel):
    """Class documentation."""
    description: str = Field(description="What was decided")
    made_by: str | None = Field(default=None, description="Speaker who stated the decision")
    context_quote: str | None = Field(default=None, description="Direct quote from transcript supporting this")
    confidence: float = Field(default=0.9, ge=0.0, le=1.0, description="Extraction confidence score")
    timestamp: float | None = Field(default=None, description="Approximate timestamp in the conversation")


class ExtractedActionItem(BaseModel):
    """Class documentation."""
    description: str = Field(description="Actionable task description")
    assignee: str | None = Field(default=None, description="Person responsible (speaker name or label)")
    deadline: date | None = Field(default=None, description="Extracted or inferred deadline")
    priority: ActionItemPriority = Field(default=ActionItemPriority.MEDIUM, description="Inferred priority level")
    confidence: float = Field(default=0.9, ge=0.0, le=1.0, description="Extraction confidence")
    source_quote: str | None = Field(default=None, description="Verbatim quote that implies this action")
    status: ActionItemStatus = Field(default=ActionItemStatus.PENDING)


class ExtractedFollowUp(BaseModel):
    """Class documentation."""
    description: str
    responsible_party: str | None = None
    due_context: str | None = Field(default=None, description="E.g., 'by next standup', 'before Friday'")
    linked_action_item_index: int | None = Field(
        default=None,
        description="Index into action_items list if this follow-up relates to an action"
    )


class AgendaItem(BaseModel):
    """Class documentation."""
    topic: str
    summary: str
    duration_seconds: float | None = None
    speakers_involved: list[str] = Field(default_factory=list)


class GenerateMOMOutput(BaseModel):
    """Class documentation."""
    session_id: UUID
    version: int = 1
    title: str = Field(description="Auto-generated meeting title")
    date: datetime | None = None
    duration_seconds: float | None = None
    attendees: list[str] = Field(default_factory=list, description="All identified speakers/participants")
    agenda_items: list[AgendaItem] = Field(default_factory=list)
    decisions: list[ExtractedDecision] = Field(default_factory=list)
    action_items: list[ExtractedActionItem] = Field(default_factory=list)
    follow_ups: list[ExtractedFollowUp] = Field(default_factory=list)
    executive_summary: str = Field(description="2-3 sentence high-level summary")
    model_used: str = Field(default="gpt-4o", description="LLM model that performed extraction")
    processing_time_ms: int = 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Tool 4: query_action_items
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class QueryActionItemsInput(BaseModel):
    """
    Retrieve and filter action items and commitments across all
    historical meetings. Supports filtering by status, assignee,
    priority, deadline, and source session.
    """

    status_filter: list[ActionItemStatus] | None = Field(
        default=None,
        description="Filter by action item status. If omitted, returns all statuses.",
    )
    assignee_filter: list[str] | None = Field(
        default=None,
        description=(
            "Filter by assignee name (case-insensitive prefix match). "
            "E.g., ['alice', 'bob']."
        ),
    )
    priority_filter: list[ActionItemPriority] | None = Field(
        default=None,
        description="Filter by priority level.",
    )
    session_id: UUID | None = Field(
        default=None,
        description="Restrict to action items from a specific session.",
    )
    deadline_before: date | None = Field(
        default=None,
        description="Only items with deadlines before this date.",
    )
    deadline_after: date | None = Field(
        default=None,
        description="Only items with deadlines after this date.",
    )
    search_text: str | None = Field(
        default=None,
        max_length=200,
        description="Full-text search within action item descriptions.",
    )
    sort_by: Literal["deadline", "priority", "created_at", "confidence"] = Field(
        default="deadline",
        description="Sort order for results.",
    )
    sort_order: Literal["asc", "desc"] = Field(default="asc")
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class ActionItemResult(BaseModel):
    """Class documentation."""
    action_item_id: UUID
    session_id: UUID
    session_title: str | None = None
    session_date: datetime | None = None
    description: str
    assignee: str | None = None
    deadline: date | None = None
    priority: ActionItemPriority = ActionItemPriority.MEDIUM
    status: ActionItemStatus = ActionItemStatus.PENDING
    confidence: float = 1.0
    source_quote: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class QueryActionItemsOutput(BaseModel):
    """Class documentation."""
    action_items: list[ActionItemResult]
    total_count: int
    filters_applied: dict[str, Any] = Field(default_factory=dict)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Tool 5: trigger_external_action
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SlackConfig(BaseModel):
    """Class documentation."""
    channel_id: str = Field(description="Slack channel ID (e.g., C01234ABCDE)")
    thread_ts: str | None = Field(
        default=None,
        description="Reply to existing thread (optional)",
    )
    mention_users: list[str] | None = Field(
        default=None,
        description="Slack user IDs to @mention",
    )


class NotionConfig(BaseModel):
    """Class documentation."""
    database_id: str = Field(description="Notion database ID to insert into")
    page_parent_id: str | None = Field(
        default=None,
        description="Parent page ID for nested page creation",
    )


class WebhookConfig(BaseModel):
    """Class documentation."""
    url: str = Field(description="Webhook endpoint URL (must be pre-registered)")
    headers: dict[str, str] | None = Field(
        default=None,
        description="Additional HTTP headers",
    )
    method: Literal["POST", "PUT"] = Field(default="POST")


class TriggerExternalActionInput(BaseModel):
    """
    Push structured MOM, action items, or summaries to external
    third-party services. All actions require human-in-the-loop
    approval unless the target is pre-approved in the policy config.

    SECURITY: The 'url' field in WebhookConfig is validated against
    an allowlist of pre-registered webhook endpoints. Arbitrary URLs
    are rejected.
    """

    target: ExternalTarget = Field(
        ...,
        description="Destination service type.",
    )
    action_type: Literal["post_mom", "post_action_items", "post_summary", "custom"] = Field(
        ...,
        description="What type of content to push.",
    )
    session_id: UUID = Field(
        ...,
        description="Source session for the content.",
    )
    content_override: str | None = Field(
        default=None,
        max_length=4000,
        description=(
            "Custom formatted content. If omitted, auto-generates "
            "from the session's existing MOM/summary."
        ),
    )
    slack_config: SlackConfig | None = Field(
        default=None,
        description="Required when target='slack'.",
    )
    notion_config: NotionConfig | None = Field(
        default=None,
        description="Required when target='notion'.",
    )
    webhook_config: WebhookConfig | None = Field(
        default=None,
        description="Required when target='webhook'.",
    )
    require_approval: bool = Field(
        default=True,
        description=(
            "If True (default), action is staged for human approval before execution. "
            "If False, executes immediately (only allowed for pre-approved targets)."
        ),
    )

    @field_validator("slack_config")
    @classmethod
    def require_slack_config(cls, v, info):
        """Method documentation."""
        if info.data.get("target") == ExternalTarget.SLACK and v is None:
            raise ValueError("slack_config is required when target='slack'")
        return v

    @field_validator("notion_config")
    @classmethod
    def require_notion_config(cls, v, info):
        """Method documentation."""
        if info.data.get("target") == ExternalTarget.NOTION and v is None:
            raise ValueError("notion_config is required when target='notion'")
        return v

    @field_validator("webhook_config")
    @classmethod
    def require_webhook_config(cls, v, info):
        """Method documentation."""
        if info.data.get("target") == ExternalTarget.WEBHOOK and v is None:
            raise ValueError("webhook_config is required when target='webhook'")
        return v


class TriggerExternalActionOutput(BaseModel):
    """Class documentation."""
    action_id: UUID = Field(description="Unique ID for tracking this external action")
    approval_status: ApprovalStatus
    target: ExternalTarget
    action_type: str
    preview_content: str = Field(description="The content that will be / was sent")
    approval_url: str | None = Field(
        default=None,
        description="URL for human to approve/reject (if pending_approval)"
    )
    delivery_status: Literal["staged", "sent", "failed"] | None = Field(
        default=None,
        description="Delivery status (null if pending approval)"
    )
    external_reference: str | None = Field(
        default=None,
        description="External ID from target (e.g., Slack message ts, Notion page ID)"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Tool Registry — OpenAI Function Calling Format
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TOOL_CATALOG: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_conversations",
            "description": (
                "Search across all transcribed conversations using hybrid semantic + lexical "
                "search with Reciprocal Rank Fusion. Use this to find specific discussions, "
                "topics, or statements across meeting history. Returns ranked transcript "
                "segments with speaker attribution and timestamps."
            ),
            "parameters": SearchConversationsInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_conversation_context",
            "description": (
                "Retrieve a windowed slice of a conversation transcript around a specific "
                "timestamp, segment, or speaker turn. Use this AFTER search_conversations "
                "to get surrounding context for a specific result, or to read a portion of "
                "a known conversation. Prevents context window blowout by returning only "
                "the relevant window."
            ),
            "parameters": FetchConversationContextInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_mom_and_actions",
            "description": (
                "Extract structured Minutes of Meeting (MOM), decisions, and typed action items "
                "from a conversation session using LLM analysis. Use this when the user asks for "
                "meeting notes, action items, or a summary of what was discussed and decided. "
                "Results are cached; use force_regenerate=true to create a fresh extraction."
            ),
            "parameters": GenerateMOMInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_action_items",
            "description": (
                "Query and filter action items and commitments across all historical meetings. "
                "Use this when the user asks about pending tasks, overdue items, what someone "
                "committed to, or status of follow-ups. Supports filtering by assignee, status, "
                "priority, deadline, and keyword search."
            ),
            "parameters": QueryActionItemsInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "trigger_external_action",
            "description": (
                "Push meeting notes, action items, or summaries to external services (Slack, "
                "Notion, Linear, or custom webhooks). IMPORTANT: This tool has side effects — "
                "it sends data to external systems. By default, all actions require human "
                "approval before execution. Only use when the user explicitly requests sharing "
                "or exporting meeting content."
            ),
            "parameters": TriggerExternalActionInput.model_json_schema(),
        },
    },
]
