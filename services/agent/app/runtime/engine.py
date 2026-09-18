"""
agent/runtime/engine.py — Agent Execution Engine

Plan-and-Execute outer loop with ReAct inner loop.
Implements tool routing, anti-hallucination guards,
hop caps, and error recovery.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable
from uuid import UUID, uuid4

from pydantic import BaseModel, ValidationError

logger = logging.getLogger("agent.runtime")

# Optional OpenTelemetry tracer
try:
    from opentelemetry import trace
    tracer = trace.get_tracer("agent.runtime")
except ImportError:
    class DummySpan:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def set_attribute(self, key, value):
            pass
        def record_exception(self, exc):
            pass
    class DummyTracer:
        def start_as_current_span(self, name, attributes=None):
            return DummySpan()
    tracer = DummyTracer()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Configuration & Types
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass(frozen=True)
class AgentConfig:
    """Runtime guardrails and limits."""
    max_total_hops: int = 15           # Maximum total tool calls per query
    max_hops_per_subgoal: int = 5      # Maximum tool calls per sub-goal
    max_planning_iterations: int = 3   # Maximum re-planning cycles
    max_tool_retries: int = 2          # Retries per individual tool call
    max_context_tokens: int = 120_000  # Context window budget
    tool_timeout_seconds: float = 30.0 # Per-tool execution timeout
    token_budget_limit: int = 200_000  # Total token spend cap per query
    enable_cot_traces: bool = True     # Log chain-of-thought reasoning


@dataclass
class ToolCall:
    """Represents a single tool invocation."""
    call_id: str
    tool_name: str
    arguments: dict[str, Any]
    raw_arguments: str = ""  # Original JSON string from LLM


@dataclass
class ToolResult:
    """Result from executing a tool."""
    call_id: str
    tool_name: str
    success: bool
    data: Any = None
    error: str | None = None
    execution_time_ms: int = 0
    token_count: int = 0


@dataclass
class AgentState:
    """Mutable execution state for a single query."""
    query_id: UUID = field(default_factory=uuid4)
    total_hops: int = 0
    total_tokens_used: int = 0
    tool_call_history: list[ToolResult] = field(default_factory=list)
    planning_iterations: int = 0
    messages: list[dict[str, Any]] = field(default_factory=list)
    sub_goals: list[str] = field(default_factory=list)
    completed_goals: list[str] = field(default_factory=list)
    final_answer: str | None = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Tool Registry & Validation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class ToolDefinition:
    name: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    executor: Callable[..., Awaitable[BaseModel]]
    description: str = ""
    requires_approval: bool = False
    side_effects: bool = False


class ToolRegistry:
    """
    Registry mapping tool names to their:
    - Input schema (Pydantic model for validation)
    - Executor function (async callable)
    - Output schema (Pydantic model for result typing)
    """

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        input_schema: type[BaseModel],
        output_schema: type[BaseModel],
        executor: Callable[..., Awaitable[BaseModel]],
        description: str = "",
        requires_approval: bool = False,
        side_effects: bool = False,
    ):
        self._tools[name] = ToolDefinition(
            name=name,
            input_schema=input_schema,
            output_schema=output_schema,
            executor=executor,
            description=description,
            requires_approval=requires_approval,
            side_effects=side_effects,
        )

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    def has_side_effects(self, name: str) -> bool:
        tool = self._tools.get(name)
        return tool.side_effects if tool else False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Policy Engine (Pre-Execution Guards)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PolicyViolation(Exception):
    """Raised when a tool call violates an execution policy."""
    pass


class PolicyEngine:
    """
    Pre-execution authorization and guardrail checks.
    Runs BEFORE every tool invocation.
    """

    def __init__(self, config: AgentConfig, webhook_allowlist: set[str] | None = None):
        self.config = config
        self.webhook_allowlist = webhook_allowlist or set()

    def check(
        self,
        tool_call: ToolCall,
        state: AgentState,
        tool_def: ToolDefinition,
    ) -> None:
        """Raises PolicyViolation if any check fails."""

        # 1. Hop cap enforcement
        if state.total_hops >= self.config.max_total_hops:
            raise PolicyViolation(
                f"Maximum tool call limit ({self.config.max_total_hops}) reached. "
                f"Synthesize a response from existing observations."
            )

        # 2. Token budget enforcement
        if state.total_tokens_used >= self.config.token_budget_limit:
            raise PolicyViolation(
                f"Token budget ({self.config.token_budget_limit}) exhausted. "
                f"Used: {state.total_tokens_used}."
            )

        # 3. Webhook URL allowlist enforcement
        if tool_call.tool_name == "trigger_external_action":
            webhook_cfg = tool_call.arguments.get("webhook_config")
            if webhook_cfg and isinstance(webhook_cfg, dict) and webhook_cfg.get("url"):
                url = webhook_cfg["url"]
                if self.webhook_allowlist and url not in self.webhook_allowlist:
                    raise PolicyViolation(
                        f"Webhook URL '{url}' is not in the allowlist. "
                        f"Register it via /admin/webhooks first."
                    )

        # 4. Side-effect confirmation
        if tool_def.requires_approval and tool_call.arguments.get("require_approval") is False:
            raise PolicyViolation(
                f"Tool '{tool_call.tool_name}' requires human approval. "
                f"Set require_approval=true or contact an admin."
            )

        # 5. Input sanitization (SQL/Prompt injection mitigation)
        self._check_injection(tool_call.arguments)

    def _check_injection(self, args: dict, depth: int = 0) -> None:
        """Recursive scan for injection patterns in tool arguments."""
        if depth > 10:
            return
        DANGEROUS_PATTERNS = [
            "'; DROP",
            "1=1 --",
            "UNION SELECT",
            "<script>",
            "{{",
            "system:",
            "ignore previous",
            "disregard all",
        ]
        for key, value in args.items():
            if isinstance(value, str):
                upper = value.upper()
                for pattern in DANGEROUS_PATTERNS:
                    if pattern.upper() in upper:
                        raise PolicyViolation(
                            f"Potential injection detected in parameter '{key}': "
                            f"blocked pattern '{pattern}'"
                        )
            elif isinstance(value, dict):
                self._check_injection(value, depth + 1)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        self._check_injection({key: item}, depth + 1)
                    elif isinstance(item, dict):
                        self._check_injection(item, depth + 1)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Agent Execution Engine
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class AgentExecutionEngine:
    """
    Core runtime loop implementing Plan-and-Execute with ReAct.
    """

    def __init__(
        self,
        llm_client: Any,
        tool_registry: ToolRegistry,
        policy_engine: PolicyEngine,
        config: AgentConfig = AgentConfig(),
    ):
        self.llm = llm_client
        self.tools = tool_registry
        self.policy = policy_engine
        self.config = config

    async def run(self, user_query: str, user_id: str) -> str:
        """
        Main entry point. Executes the full agent loop for a user query.
        Returns the final synthesized response string.
        """
        with tracer.start_as_current_span("agent.run") as span:
            state = AgentState()
            span.set_attribute("query_id", str(state.query_id))
            span.set_attribute("user_id", user_id)
            span.set_attribute("user_query", user_query)

            state.messages = [
                {"role": "system", "content": self._build_system_prompt()},
                {"role": "user", "content": user_query},
            ]

            try:
                while state.planning_iterations < self.config.max_planning_iterations:
                    state.planning_iterations += 1

                    with tracer.start_as_current_span("agent.plan") as plan_span:
                        plan_span.set_attribute("iteration", state.planning_iterations)

                        await self._react_loop(state)

                        if state.final_answer is not None:
                            break

                        if state.total_hops >= self.config.max_total_hops:
                            state.final_answer = await self._force_synthesize(state)
                            break

                if state.final_answer is None:
                    state.final_answer = await self._force_synthesize(state)

                span.set_attribute("total_hops", state.total_hops)
                span.set_attribute("total_tokens", state.total_tokens_used)
                span.set_attribute("tool_calls_count", len(state.tool_call_history))

                return state.final_answer

            except PolicyViolation as e:
                logger.warning("Policy violation in query %s: %s", state.query_id, e)
                return f"I couldn't complete that request: {e}"
            except Exception as e:
                logger.exception("Agent error in query %s", state.query_id)
                return (
                    "I encountered an unexpected error processing your request. "
                    "Please try again or rephrase your question."
                )

    async def _react_loop(self, state: AgentState) -> None:
        """
        Inner ReAct loop: repeatedly call LLM → parse tool calls →
        execute → feed back observations.
        """
        hops_this_subgoal = 0

        while (
            hops_this_subgoal < self.config.max_hops_per_subgoal
            and state.total_hops < self.config.max_total_hops
        ):
            with tracer.start_as_current_span("agent.react_step") as step_span:
                step_span.set_attribute("hop", state.total_hops)

                response = await self._call_llm(state)
                message = response.choices[0].message
                
                # Append assistant message
                msg_dict = {"role": "assistant", "content": message.content}
                if hasattr(message, "tool_calls") and message.tool_calls:
                    msg_dict["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            }
                        }
                        for tc in message.tool_calls
                    ]
                state.messages.append(msg_dict)

                if hasattr(response, "usage") and response.usage:
                    state.total_tokens_used += response.usage.total_tokens

                if not hasattr(message, "tool_calls") or not message.tool_calls:
                    state.final_answer = message.content or "Task completed."
                    return

                for tc in message.tool_calls:
                    state.total_hops += 1
                    hops_this_subgoal += 1

                    raw_args = tc.function.arguments
                    try:
                        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except Exception:
                        args = {}

                    tool_call = ToolCall(
                        call_id=tc.id,
                        tool_name=tc.function.name,
                        arguments=args,
                        raw_arguments=str(raw_args),
                    )

                    result = await self._execute_tool(tool_call, state)
                    state.tool_call_history.append(result)

                    state.messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": self._format_tool_result(result),
                    })

                    step_span.set_attribute(f"tool.{tool_call.tool_name}.success", result.success)

    async def _execute_tool(self, tool_call: ToolCall, state: AgentState) -> ToolResult:
        with tracer.start_as_current_span(f"tool.{tool_call.tool_name}") as tool_span:
            tool_span.set_attribute("tool.call_id", tool_call.call_id)
            tool_span.set_attribute("tool.arguments", tool_call.raw_arguments)
            start = time.monotonic()

            tool_def = self.tools.get(tool_call.tool_name)
            if tool_def is None:
                error_msg = (
                    f"Tool '{tool_call.tool_name}' does not exist. "
                    f"Available tools: {self.tools.list_names()}"
                )
                tool_span.set_attribute("tool.error", "unknown_tool")
                return ToolResult(
                    call_id=tool_call.call_id,
                    tool_name=tool_call.tool_name,
                    success=False,
                    error=error_msg,
                )

            try:
                validated_input = tool_def.input_schema.model_validate(tool_call.arguments)
            except ValidationError as e:
                error_msg = f"Invalid arguments for '{tool_call.tool_name}': {e}"
                tool_span.set_attribute("tool.error", "validation_error")
                return ToolResult(
                    call_id=tool_call.call_id,
                    tool_name=tool_call.tool_name,
                    success=False,
                    error=error_msg,
                    execution_time_ms=int((time.monotonic() - start) * 1000),
                )

            try:
                self.policy.check(tool_call, state, tool_def)
            except PolicyViolation as e:
                tool_span.set_attribute("tool.error", "policy_violation")
                return ToolResult(
                    call_id=tool_call.call_id,
                    tool_name=tool_call.tool_name,
                    success=False,
                    error=f"Policy violation: {e}",
                    execution_time_ms=int((time.monotonic() - start) * 1000),
                )

            last_error = None
            for attempt in range(1, self.config.max_tool_retries + 1):
                try:
                    import asyncio
                    result_model = await asyncio.wait_for(
                        tool_def.executor(validated_input),
                        timeout=self.config.tool_timeout_seconds,
                    )
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    tool_span.set_attribute("tool.success", True)
                    tool_span.set_attribute("tool.execution_time_ms", elapsed_ms)

                    data = result_model.model_dump() if hasattr(result_model, "model_dump") else result_model
                    return ToolResult(
                        call_id=tool_call.call_id,
                        tool_name=tool_call.tool_name,
                        success=True,
                        data=data,
                        execution_time_ms=elapsed_ms,
                    )

                except asyncio.TimeoutError:
                    last_error = f"Tool '{tool_call.tool_name}' timed out after {self.config.tool_timeout_seconds}s"
                except ValidationError as e:
                    last_error = f"Output schema validation failed: {e}"
                    break
                except Exception as e:
                    last_error = f"Execution error: {type(e).__name__}: {e}"

            tool_span.set_attribute("tool.error", "execution_failed")
            return ToolResult(
                call_id=tool_call.call_id,
                tool_name=tool_call.tool_name,
                success=False,
                error=last_error or "Unknown error",
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

    async def _call_llm(self, state: AgentState) -> Any:
        from app.tools.schemas import TOOL_CATALOG

        if self.llm is not None:
            return await self.llm.chat.completions.create(
                model="gpt-4o",
                messages=state.messages,
                tools=TOOL_CATALOG,
                tool_choice="auto",
                temperature=0.1,
                max_tokens=4096,
            )

        # Fallback if no LLM client is configured (e.g. unit testing/dry run)
        class MockChoice:
            def __init__(self, content):
                self.message = type("Msg", (), {"content": content, "tool_calls": []})()
        class MockResponse:
            def __init__(self, content):
                self.choices = [MockChoice(content)]
                self.usage = type("Usage", (), {"total_tokens": 10})()

        last_user = state.messages[-1].get("content", "")
        return MockResponse(f"Analysis completed for query: {last_user}")

    async def _force_synthesize(self, state: AgentState) -> str:
        state.messages.append({
            "role": "user",
            "content": (
                "[SYSTEM] You have reached the maximum number of tool calls. "
                "Synthesize a complete response to the user's original question "
                "using ONLY the tool results gathered so far."
            ),
        })
        if self.llm is not None:
            resp = await self.llm.chat.completions.create(
                model="gpt-4o",
                messages=state.messages,
                tools=[],
                temperature=0.3,
                max_tokens=4096,
            )
            return resp.choices[0].message.content
        return "Synthesized answer based on available conversation data."

    def _build_system_prompt(self) -> str:
        return """You are a Conversation Intelligence Agent for a meeting recording system.
You have access to a database of transcribed conversations with speaker diarization,
semantic search, and AI-extracted meeting intelligence.

## Tool Use Guidelines
1. **search_conversations**: Use FIRST to find relevant meetings/segments.
2. **fetch_conversation_context**: Use AFTER search to get surrounding transcript context.
3. **generate_mom_and_actions**: Use when asked for meeting notes, summaries, or action items.
4. **query_action_items**: Use for questions about tasks, commitments, deadlines across meetings.
5. **trigger_external_action**: Use ONLY when explicitly asked to share/export content.

## Anti-Hallucination Rules
- NEVER fabricate meeting content, speaker names, or dates.
- Cite specific timestamps and speaker labels from tool results."""

    def _format_tool_result(self, result: ToolResult) -> str:
        if result.success:
            data_str = json.dumps(result.data, default=str)
            if len(data_str) > 8000:
                data_str = data_str[:8000] + "\n... [TRUNCATED — use more specific filters]"
            return data_str
        else:
            return json.dumps({
                "error": True,
                "tool_name": result.tool_name,
                "message": result.error,
            })
