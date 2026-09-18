"""
agent/api/v1/agent.py — Agent Query API Endpoint
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.runtime.engine import (
    AgentExecutionEngine,
    ToolRegistry,
    AgentConfig,
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
    user_id: str
    conversation_id: str | None = None


class AgentQueryResponse(BaseModel):
    response: str
    query_id: str
    tool_calls_count: int
    tokens_used: int
    latency_ms: int


def build_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()

    registry.register(
        name="search_conversations",
        input_schema=SearchConversationsInput,
        output_schema=SearchConversationsOutput,
        executor=execute_search_conversations,
        description="Hybrid search across transcribed conversations with RRF",
        side_effects=False,
    )
    registry.register(
        name="fetch_conversation_context",
        input_schema=FetchConversationContextInput,
        output_schema=FetchConversationContextOutput,
        executor=execute_fetch_context,
        description="Windowed transcript retrieval around a timestamp or turns",
        side_effects=False,
    )
    registry.register(
        name="generate_mom_and_actions",
        input_schema=GenerateMOMInput,
        output_schema=GenerateMOMOutput,
        executor=execute_generate_mom,
        description="Extract MOM, decisions, and action items via LLM",
        side_effects=False,
    )
    registry.register(
        name="query_action_items",
        input_schema=QueryActionItemsInput,
        output_schema=QueryActionItemsOutput,
        executor=execute_query_action_items,
        description="Query action items across historical meetings",
        side_effects=False,
    )
    registry.register(
        name="trigger_external_action",
        input_schema=TriggerExternalActionInput,
        output_schema=TriggerExternalActionOutput,
        executor=execute_trigger_external,
        description="Push content to Slack/Notion/Webhooks",
        requires_approval=True,
        side_effects=True,
    )

    return registry


@router.post("/query", response_model=AgentQueryResponse)
async def query_agent(req: AgentQueryRequest):
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

    registry = build_tool_registry()
    policy = PolicyEngine(config, webhook_allowlist=set(settings.webhook_allowlist))

    llm_client = None
    try:
        import litellm
        llm_client = litellm
    except Exception:
        pass

    engine = AgentExecutionEngine(
        llm_client=llm_client,
        tool_registry=registry,
        policy_engine=policy,
        config=config,
    )

    try:
        response_text = await engine.run(req.query, req.user_id)
        latency_ms = int((time.time() - start_time) * 1000)

        return AgentQueryResponse(
            response=response_text,
            query_id=query_id,
            tool_calls_count=0,
            tokens_used=0,
            latency_ms=latency_ms,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
