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
        import os
        import httpx

        # 1. Check if Ollama is enabled
        use_ollama = os.getenv("USE_OLLAMA", "true").lower() in ("true", "1", "yes") or \
                     os.getenv("AGENT_USE_OLLAMA", "true").lower() in ("true", "1", "yes")
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
        ollama_model = os.getenv("OLLAMA_MODEL") or os.getenv("AGENT_OLLAMA_MODEL") or "llama3.2:3b"

        if use_ollama:
            try:
                ollama_messages = []
                for m in state.messages:
                    r = m.get("role", "user")
                    if r not in ("system", "user", "assistant"):
                        r = "user"
                    ollama_messages.append({"role": r, "content": str(m.get("content", ""))})

                url = f"{ollama_url.rstrip('/')}/api/chat"
                payload = {
                    "model": ollama_model,
                    "messages": ollama_messages,
                    "stream": False,
                    "options": {"temperature": 0.2}
                }
                async with httpx.AsyncClient(timeout=45.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        txt = data.get("message", {}).get("content", "")
                        if txt:
                            class OllamaChoice:
                                def __init__(self, content):
                                    self.message = type("Msg", (), {"content": content, "tool_calls": []})()
                            class OllamaResponse:
                                def __init__(self, content):
                                    self.choices = [OllamaChoice(content)]
                                    self.usage = type("Usage", (), {"total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0)})()
                            logger.info("ollama_agent_call_success", extra={"model": ollama_model})
                            return OllamaResponse(txt)
            except Exception as e:
                logger.warning("ollama_agent_call_failed: %s", e)

        # 2. Fallback to Gemini if configured
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            # Format contents for Google Gemini API
            contents = []
            for m in state.messages:
                role = "user" if m.get("role") in ["user", "system"] else "model"
                contents.append({"role": role, "parts": [{"text": str(m.get("content", ""))}]})

            for m_name in ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash"]:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{m_name}:generateContent?key={gemini_key}"
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        resp = await client.post(url, json={"contents": contents})
                        if resp.status_code == 200:
                            data = resp.json()
                            txt = data["candidates"][0]["content"]["parts"][0]["text"]
                            class GeminiChoice:
                                def __init__(self, content):
                                    self.message = type("Msg", (), {"content": content, "tool_calls": []})()
                            class GeminiResponse:
                                def __init__(self, content):
                                    self.choices = [GeminiChoice(content)]
                                    self.usage = type("Usage", (), {"total_tokens": data.get("usageMetadata", {}).get("totalTokenCount", 50)})()
                            return GeminiResponse(txt)
                except Exception as e:
                    logger.warning("gemini_agent_call_failed", model=m_name, error=str(e))

        # Check if an OpenAI or other LLM API key is present
        has_api_key = bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))

        if self.llm is not None and has_api_key:
            try:
                model = os.getenv("LLM_MODEL", "gpt-4o")
                response = await self.llm.acompletion(
                    model=model,
                    messages=state.messages,
                    tools=TOOL_CATALOG,
                    tool_choice="auto",
                    temperature=0.1,
                    max_tokens=4096,
                )
                return response
            except Exception as e:
                logger.warning("LLM acompletion error: %s, falling back to autonomous tool reasoning", e)

        # Autonomous tool reasoning fallback (uses DB tools directly)
        return await self._fallback_tool_reasoning(state)

    async def _fallback_tool_reasoning(self, state: AgentState) -> Any:
        """Autonomously executes tools against PostgreSQL data and synthesizes Hinglish response."""
        class FallbackChoice:
            def __init__(self, content):
                self.message = type("Msg", (), {"content": content, "tool_calls": []})()
        class FallbackResponse:
            def __init__(self, content):
                self.choices = [FallbackChoice(content)]
                self.usage = type("Usage", (), {"total_tokens": 15})()

        user_query = ""
        for m in reversed(state.messages):
            if m.get("role") == "user" and not str(m.get("content", "")).startswith("[SYSTEM]"):
                user_query = str(m.get("content", ""))
                break

        q = user_query.lower()

        # 1. Greetings
        if any(w in q for w in ["hello", "hi", "hey", "kaise ho", "kya haal", "namaste", "help", "who are you"]):
            msg = (
                "Namaste! Main ProHuman ka ReAct Conversation Agent hoon.\n\n"
                "Main aapke recorded meetings ko analyze kar sakta hoon, jaise:\n"
                "• **Conversations search karna** (e.g. *'What was discussed about budget?'*)\n"
                "• **Action items nikalna** (e.g. *'Show all pending tasks'*)\n"
                "• **MOM & Decisions dekhna** (e.g. *'Recent meeting ka summary kya hai?'*)\n\n"
                "Aap mujhse koi bhi question pooch sakte hain!"
            )
            return FallbackResponse(msg)

        # 2. Action items / tasks query
        if any(w in q for w in ["action", "task", "todo", "kaam", "deadline", "pending", "assignee"]):
            try:
                from app.tools.schemas import QueryActionItemsInput
                from app.tools.executors import execute_query_action_items
                result = await execute_query_action_items(QueryActionItemsInput(limit=10))
                items = result.action_items
                if items:
                    lines = [f"Found **{len(items)} action items** from your recorded meetings:\n"]
                    for idx, it in enumerate(items, 1):
                        assignee_str = f" (Assignee: **{it.assignee}**)" if it.assignee else ""
                        priority_str = f" [{it.priority.upper()}]" if it.priority else ""
                        lines.append(f"{idx}. {it.description}{assignee_str}{priority_str} — *Status: {it.status}*")
                    return FallbackResponse("\n".join(lines))
                else:
                    return FallbackResponse("Filhal database me koi pending action items nahi mile. Jab aap meeting record karenge to action items yahan automatically track ho jayenge.")
            except Exception as e:
                logger.warning("Error fetching action items: %s", e)

        # 3. Meeting search / summary / MOM
        try:
            from app.tools.schemas import SearchConversationsInput, SearchMode
            from app.tools.executors import execute_search_conversations
            search_res = await execute_search_conversations(
                SearchConversationsInput(query=user_query, limit=5, search_mode=SearchMode.LEXICAL)
            )
            if search_res.results:
                lines = [f"Aapki query '**{user_query}**' ke liye conversations me se relevant segments mile hain:\n"]
                for r in search_res.results[:5]:
                    lines.append(f"• **{r.speaker_label}** [{r.start_time:.1f}s - {r.end_time:.1f}s]: \"{r.text}\"")
                lines.append("\nAap specific speaker ya time context ke baare me bhi pooch sakte hain.")
                return FallbackResponse("\n".join(lines))
        except Exception as e:
            logger.warning("Search tool fallback error: %s", e)

        # 4. Fallback to latest meeting details from DB
        try:
            from packages.db.engine import get_db_context
            from packages.db.repositories.session_repo import SessionRepository
            from packages.db.repositories.feature_repo import FeatureRepository
            from packages.db.repositories.transcript_repo import TranscriptRepository

            async with get_db_context() as db_session:
                sess_repo = SessionRepository(db_session)
                feat_repo = FeatureRepository(db_session)
                trans_repo = TranscriptRepository(db_session)

                sessions, _ = await sess_repo.list_sessions(limit=1, offset=0)
                if sessions:
                    latest = sessions[0]
                    mom = await feat_repo.get_by_session_and_name(latest.id, "mom")
                    segs = await trans_repo.get_by_session(latest.id)

                    response_parts = [f"**Latest Meeting Summary ({latest.device_id})**:"]
                    if mom and mom.data:
                        d = mom.data
                        if d.get("title"): response_parts.append(f"**Title:** {d.get('title')}")
                        if d.get("executive_summary"): response_parts.append(f"**Summary:** {d.get('executive_summary')}")
                        if d.get("decisions"):
                            decs = [f"- {item.get('description', '')}" for item in d.get("decisions", [])]
                            if decs: response_parts.append("**Decisions:**\n" + "\n".join(decs))
                        if d.get("action_items"):
                            acts = [f"- {item.get('description', '')}" for item in d.get("action_items", [])]
                            if acts: response_parts.append("**Action Items:**\n" + "\n".join(acts))
                    elif segs:
                        preview = " ".join([s.text for s in segs[:4]])
                        response_parts.append(f"**Transcript Preview:** \"{preview}\"")
                    else:
                        response_parts.append("Session record ho chuka hai, par abhi tak transcript ya MOM extract nahi hua hai.")

                    return FallbackResponse("\n\n".join(response_parts))
        except Exception as e:
            logger.warning("DB query fallback error: %s", e)

        return FallbackResponse(
            f"Maine aapka request '{user_query}' process kiya. Aap meeting transcribe karke 'Transcript & MOM' tab me dekh sakte hain, ya action items query kar sakte hain."
        )

    async def _force_synthesize(self, state: AgentState) -> str:
        state.messages.append({
            "role": "user",
            "content": (
                "[SYSTEM] Synthesize a complete response to the user's original question "
                "using the tool results gathered so far in Hinglish."
            ),
        })
        import os
        import httpx

        use_ollama = os.getenv("USE_OLLAMA", "true").lower() in ("true", "1", "yes") or \
                     os.getenv("AGENT_USE_OLLAMA", "true").lower() in ("true", "1", "yes")
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
        ollama_model = os.getenv("OLLAMA_MODEL") or os.getenv("AGENT_OLLAMA_MODEL") or "llama3.2:3b"

        if use_ollama:
            try:
                ollama_messages = [
                    {"role": m.get("role", "user") if m.get("role") in ("system", "user", "assistant") else "user", 
                     "content": str(m.get("content", ""))} 
                    for m in state.messages
                ]
                url = f"{ollama_url.rstrip('/')}/api/chat"
                payload = {
                    "model": ollama_model,
                    "messages": ollama_messages,
                    "stream": False,
                    "options": {"temperature": 0.3}
                }
                async with httpx.AsyncClient(timeout=45.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        txt = data.get("message", {}).get("content", "")
                        if txt:
                            return txt
            except Exception as e:
                logger.warning("ollama_force_synthesize_failed: %s", e)

        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            try:
                contents = []
                for m in state.messages:
                    role = "user" if m.get("role") in ["user", "system"] else "model"
                    contents.append({"role": role, "parts": [{"text": str(m.get("content", ""))}]})
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={gemini_key}"
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(url, json={"contents": contents})
                    if resp.status_code == 200:
                        data = resp.json()
                        return data["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as e:
                logger.warning("gemini_force_synthesize_failed: %s", e)

        has_api_key = bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))
        if self.llm is not None and has_api_key:
            try:
                model = os.getenv("LLM_MODEL", "gpt-4o")
                resp = await self.llm.acompletion(
                    model=model,
                    messages=state.messages,
                    tools=[],
                    temperature=0.3,
                    max_tokens=4096,
                )
                return resp.choices[0].message.content
            except Exception:
                pass
        
        # If no LLM, return synthesized fallback
        fb = await self._fallback_tool_reasoning(state)
        return fb.choices[0].message.content

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
