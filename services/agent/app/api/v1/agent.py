"""
agent/api/v1/agent.py — Agent Query API Endpoint
"""

from __future__ import annotations

import time
import uuid
from functools import partial
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from packages.access import Principal, require_member
from pydantic import BaseModel, Field
from packages.contracts.evidence import TranscriptEvidence

from app.runtime.engine import (
    AgentExecutionEngine,
    ToolRegistry,
    AgentConfig,
    AgentState,
    PolicyEngine,
)
from app.config import get_settings
from app.tools.schemas import (
    SearchConversationsInput,
    SearchConversationsOutput,
    FetchConversationContextInput,
    FetchConversationContextOutput,
    GenerateMOMInput,
    GenerateMOMOutput,
    QueryActionItemsInput,
    QueryActionItemsOutput,
    TriggerExternalActionInput,
    TriggerExternalActionOutput,
)
from app.tools.executors import (
    execute_search_conversations,
    execute_fetch_context,
    execute_generate_mom,
    execute_query_action_items,
    execute_trigger_external,
)

router = APIRouter()


class AgentQueryRequest(BaseModel):
    query: str
    conversation_id: str | None = None


class AgentQueryResponse(BaseModel):
    response: str
    query_id: str
    tool_calls_count: int
    tokens_used: int
    latency_ms: int
    citations: list[TranscriptEvidence] = Field(default_factory=list)


def build_tool_registry(workspace_id: UUID) -> ToolRegistry:
    registry = ToolRegistry()

    registry.register(
        name="search_conversations",
        input_schema=SearchConversationsInput,
        output_schema=SearchConversationsOutput,
        executor=partial(execute_search_conversations, workspace_id=workspace_id),
        description="Hybrid search across transcribed conversations with RRF",
        side_effects=False,
    )
    registry.register(
        name="fetch_conversation_context",
        input_schema=FetchConversationContextInput,
        output_schema=FetchConversationContextOutput,
        executor=partial(execute_fetch_context, workspace_id=workspace_id),
        description="Windowed transcript retrieval around a timestamp or turns",
        side_effects=False,
    )
    registry.register(
        name="generate_mom_and_actions",
        input_schema=GenerateMOMInput,
        output_schema=GenerateMOMOutput,
        executor=partial(execute_generate_mom, workspace_id=workspace_id),
        description="Extract MOM, decisions, and action items via LLM",
        side_effects=False,
    )
    registry.register(
        name="query_action_items",
        input_schema=QueryActionItemsInput,
        output_schema=QueryActionItemsOutput,
        executor=partial(execute_query_action_items, workspace_id=workspace_id),
        description="Query action items across historical meetings",
        side_effects=False,
    )
    registry.register(
        name="trigger_external_action",
        input_schema=TriggerExternalActionInput,
        output_schema=TriggerExternalActionOutput,
        executor=partial(execute_trigger_external, workspace_id=workspace_id),
        description="Push content to Slack/Notion/Webhooks",
        requires_approval=True,
        side_effects=True,
    )

    return registry


@router.post("/query", response_model=AgentQueryResponse)
async def query_agent(req: AgentQueryRequest, principal: Principal = Depends(require_member)):
    """
    Main conversational agent endpoint.
    Executes the Plan-and-Execute with ReAct runtime across conversation memory.
    """
    start_time = time.time()
    query_id = str(uuid.uuid4())
    settings = get_settings()

    config = AgentConfig(
        max_total_hops=settings.max_total_hops,
        max_hops_per_subgoal=settings.max_hops_per_subgoal,
        max_planning_iterations=settings.max_planning_iterations,
        max_tool_retries=settings.max_tool_retries,
        tool_timeout_seconds=settings.tool_timeout_seconds,
        token_budget_limit=settings.token_budget_limit,
    )

    registry = build_tool_registry(principal.workspace_id)
    policy = PolicyEngine(config, webhook_allowlist=set(settings.webhook_allowlist))

    llm_client = None
    try:
        import litellm
        llm_client = litellm
    except ImportError:
        pass

    engine = AgentExecutionEngine(
        llm_client=llm_client,
        tool_registry=registry,
        policy_engine=policy,
        config=config,
    )

    try:
        state = AgentState()
        response = await engine.run(
            req.query, f"{principal.workspace_id}:{principal.user_id}",
            state=state, workspace_id=principal.workspace_id,
        )
        response_text, citations = state.cited_answer(response)
        if not citations and req.query.casefold().strip(" !?.") not in {
            "hello", "hi", "hey", "namaste", "help", "who are you", "kaise ho", "kya haal"
        }:
            response_text = "I couldn’t verify an answer from the available transcript excerpts."
        latency_ms = int((time.time() - start_time) * 1000)

        return AgentQueryResponse(
            response=response_text,
            query_id=query_id,
            tool_calls_count=state.total_hops,
            tokens_used=state.total_tokens_used,
            citations=citations,
            latency_ms=latency_ms,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Agent query failed") from e
