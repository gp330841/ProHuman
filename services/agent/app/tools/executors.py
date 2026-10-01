"""
agent/tools/executors.py — Tool Executor Implementations

Connects Agent Tool calls to DB Repositories, LiteLLM/Instructor, and external services.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, date
from typing import Any
from uuid import UUID

from packages.db.engine import get_db_context
from packages.db.repositories.transcript_repo import TranscriptRepository
from packages.db.repositories.session_repo import SessionRepository
from packages.db.repositories.feature_repo import FeatureRepository

from app.tools.schemas import (
    SearchConversationsInput,
    SearchConversationsOutput,
    SearchMode,
    SearchResultSegment,
    FetchConversationContextInput,
    FetchConversationContextOutput,
    ContextSegment,
    ContextWindowMode,
    GenerateMOMInput,
    GenerateMOMOutput,
    AgendaItem,
    ExtractedDecision,
    ExtractedActionItem,
    ExtractedFollowUp,
    QueryActionItemsInput,
    QueryActionItemsOutput,
    ActionItemResult,
    TriggerExternalActionInput,
    TriggerExternalActionOutput,
    ApprovalStatus,
    ExternalTarget,
)


async def execute_search_conversations(
    input: SearchConversationsInput,
) -> SearchConversationsOutput:
    """Execute hybrid search using pgvector and PostgreSQL full-text search."""
    query_embedding = [0.0] * 1536
    if input.search_mode != SearchMode.LEXICAL:
        import litellm
        resp = await litellm.aembedding(
            model="text-embedding-3-small",
            input=[input.query],
        )
        if not resp.data:
            raise RuntimeError("Embedding service returned no vector")
        query_embedding = resp.data[0]["embedding"]

    async with get_db_context() as session:
        repo = TranscriptRepository(session)
        rows = await repo.hybrid_search(
            query_text=input.query,
            query_embedding=query_embedding,
            limit=input.limit,
            offset=input.offset,
            session_ids=input.session_ids,
            time_range_start=input.time_range_start,
            time_range_end=input.time_range_end,
            search_mode=input.search_mode.value.upper(),
        )

        results: list[SearchResultSegment] = []
        for row in rows:
            seg_id = row.get("segment_id")
            if isinstance(seg_id, str):
                seg_id = UUID(seg_id)
            sess_id = row.get("session_id")
            if isinstance(sess_id, str):
                sess_id = UUID(sess_id)

            results.append(
                SearchResultSegment(
                    segment_id=seg_id or uuid.uuid4(),
                    session_id=sess_id or uuid.uuid4(),
                    speaker_label=row.get("speaker_label", "speaker_0"),
                    text=row.get("text", ""),
                    start_time=float(row.get("start_time", 0.0)),
                    end_time=float(row.get("end_time", 0.0)),
                    rrf_score=float(row.get("rrf_score", 0.0)),
                    vector_rank=row.get("vector_rank"),
                    text_rank=row.get("text_rank"),
                    session_date=row.get("created_at"),
                )
            )

        return SearchConversationsOutput(
            results=results,
            total_count=len(results),
            query_embedding_model="text-embedding-3-small",
            search_mode_used=input.search_mode,
        )


async def execute_fetch_context(
    input: FetchConversationContextInput,
) -> FetchConversationContextOutput:
    """Retrieve windowed transcript segments around a timestamp, segment ID, or turns."""
    async with get_db_context() as session:
        repo = TranscriptRepository(session)
        all_segments = await repo.get_by_session(input.session_id, order_by_index=True)

        if not all_segments:
            return FetchConversationContextOutput(
                session_id=input.session_id,
                window_start_time=0.0,
                window_end_time=0.0,
                segments=[],
                speakers_in_window=[],
                truncated=False,
            )

        anchor_time = 0.0
        if input.mode == ContextWindowMode.TIMESTAMP and input.anchor_timestamp is not None:
            anchor_time = input.anchor_timestamp
        elif input.anchor_segment_id is not None:
            for s in all_segments:
                if s.id == input.anchor_segment_id:
                    anchor_time = s.start_time
                    break

        w_start = max(0.0, anchor_time - input.window_seconds)
        w_end = anchor_time + input.window_seconds

        matched = [
            s for s in all_segments
            if (s.start_time <= w_end and s.end_time >= w_start)
        ]

        if input.speaker_filter:
            matched = [s for s in matched if s.speaker_label in input.speaker_filter]

        speakers = list({s.speaker_label for s in matched})
        context_segs = [
            ContextSegment(
                segment_id=s.id,
                segment_index=s.segment_index,
                speaker_label=s.speaker_label,
                text=s.text,
                start_time=s.start_time,
                end_time=s.end_time,
                confidence=s.confidence,
                word_timestamps=s.word_timestamps if input.include_word_timestamps else None,
            )
            for s in matched
        ]

        return FetchConversationContextOutput(
            session_id=input.session_id,
            window_start_time=w_start,
            window_end_time=w_end,
            segments=context_segs,
            speakers_in_window=speakers,
            truncated=False,
        )


async def execute_generate_mom(
    input: GenerateMOMInput,
) -> GenerateMOMOutput:
    """Extract Minutes of Meeting, decisions, and action items using LLM and cached feature results."""
    async with get_db_context() as session:
        feat_repo = FeatureRepository(session)
        if not input.force_regenerate:
            cached = await feat_repo.get_by_session_and_name(input.session_id, "mom")
            if cached and cached.data:
                d = cached.data
                return GenerateMOMOutput(
                    session_id=input.session_id,
                    version=cached.version,
                    title=d.get("title", "Meeting MOM"),
                    date=datetime.utcnow(),
                    duration_seconds=d.get("duration_seconds"),
                    attendees=d.get("attendees", []),
                    agenda_items=[AgendaItem(**a) for a in d.get("agenda_items", [])],
                    decisions=[ExtractedDecision(**dec) for dec in d.get("decisions", [])],
                    action_items=[ExtractedActionItem(**act) for act in d.get("action_items", [])],
                    follow_ups=[ExtractedFollowUp(**fu) for fu in d.get("follow_ups", [])],
                    executive_summary=d.get("executive_summary", "Summary not available."),
                    model_used=cached.provider_model or "gpt-4o",
                )

        trans_repo = TranscriptRepository(session)
        segments = await trans_repo.get_by_session(input.session_id)
        if not segments:
            raise ValueError(f"No transcript exists for session {input.session_id}")
        transcript_text = "\n".join([f"{s.speaker_label}: {s.text}" for s in segments])

        import litellm

        messages = [
            {
                "role": "system",
                "content": (
                    "Extract meeting notes as JSON with title, attendees, agenda_items, "
                    "decisions, action_items, follow_ups, and executive_summary. "
                    "Use only facts supported by the transcript."
                ),
            },
            {"role": "user", "content": transcript_text[:12000]},
        ]
        response = await litellm.acompletion(
            model="gpt-4o",
            messages=messages,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("The LLM returned an empty meeting-notes response")
        mom_data = json.loads(content)

        next_ver = await feat_repo.get_latest_version(input.session_id, "mom") + 1
        await feat_repo.create(
            session_id=input.session_id,
            feature_name="mom",
            version=next_ver,
            data=mom_data,
            provider_model="gpt-4o",
        )

        return GenerateMOMOutput(
            session_id=input.session_id,
            version=next_ver,
            title=mom_data["title"],
            date=datetime.utcnow(),
            attendees=mom_data.get("attendees", []),
            agenda_items=[AgendaItem(**a) for a in mom_data.get("agenda_items", [])],
            decisions=[ExtractedDecision(**dec) for dec in mom_data.get("decisions", [])],
            action_items=[ExtractedActionItem(**act) for act in mom_data.get("action_items", [])],
            follow_ups=[ExtractedFollowUp(**fu) for fu in mom_data.get("follow_ups", [])],
            executive_summary=mom_data["executive_summary"],
        )


async def execute_query_action_items(
    input: QueryActionItemsInput,
) -> QueryActionItemsOutput:
    """Retrieve historical action items across meetings with multi-criteria filtering."""
    async with get_db_context() as session:
        feat_repo = FeatureRepository(session)
        sess_repo = SessionRepository(session)

        sessions_to_query = [input.session_id] if input.session_id else []
        if not sessions_to_query:
            all_s, _ = await sess_repo.list_sessions(limit=50, offset=0)
            sessions_to_query = [s.id for s in all_s]

        items: list[ActionItemResult] = []
        for s_id in sessions_to_query:
            feats = await feat_repo.list_by_session(s_id)
            for f in feats:
                if f.feature_name in ("action_items", "mom") and isinstance(f.data, dict):
                    raw_items = f.data.get("action_items") or f.data.get("items") or []
                    for idx, raw in enumerate(raw_items):
                        desc = raw.get("description", "")
                        assignee = raw.get("assignee")
                        status = raw.get("status", "pending")
                        priority = raw.get("priority", "medium")

                        if input.status_filter and status not in [s.value for s in input.status_filter]:
                            continue
                        if input.assignee_filter and assignee and not any(af.lower() in assignee.lower() for af in input.assignee_filter):
                            continue
                        if input.search_text and input.search_text.lower() not in desc.lower():
                            continue

                        items.append(
                            ActionItemResult(
                                action_item_id=uuid.uuid5(s_id, f"action_{idx}"),
                                session_id=s_id,
                                description=desc,
                                assignee=assignee,
                                status=status,
                                priority=priority,
                                confidence=float(raw.get("confidence", 0.9)),
                                source_quote=raw.get("source_quote"),
                                created_at=f.created_at,
                            )
                        )

        total = len(items)
        paginated = items[input.offset : input.offset + input.limit]
        return QueryActionItemsOutput(action_items=paginated, total_count=total)


async def execute_trigger_external(
    input: TriggerExternalActionInput,
) -> TriggerExternalActionOutput:
    """Push structured MOM or tasks to external endpoints (Slack, Notion, Webhooks)."""
    action_id = uuid.uuid4()
    preview = input.content_override or f"Pushing meeting intelligence for session {input.session_id}"

    if input.require_approval:
        return TriggerExternalActionOutput(
            action_id=action_id,
            approval_status=ApprovalStatus.PENDING_APPROVAL,
            target=input.target,
            action_type=input.action_type,
            preview_content=preview,
            approval_url=f"https://api.prohuman.ai/approvals/{action_id}",
            delivery_status="staged",
        )

    if input.target != ExternalTarget.WEBHOOK or not input.webhook_config:
        raise NotImplementedError(f"External delivery to {input.target.value} is not configured")

    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.post(
            input.webhook_config.url,
            json={"session_id": str(input.session_id), "content": preview},
            headers=input.webhook_config.headers or {},
            timeout=10.0,
        )
        response.raise_for_status()

    return TriggerExternalActionOutput(
        action_id=action_id,
        approval_status=ApprovalStatus.AUTO_APPROVED,
        target=input.target,
        action_type=input.action_type,
        preview_content=preview,
        delivery_status="sent",
        external_reference=f"ext_{action_id.hex[:8]}",
    )
