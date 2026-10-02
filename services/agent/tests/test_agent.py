"""Unit tests for Agent Service runtime, policies, and tools."""
from __future__ import annotations

import pytest
from pydantic import BaseModel

from app.config import AgentSettings, get_settings
from app.runtime.engine import (
    AgentConfig,
    AgentState,
    PolicyEngine,
    PolicyViolation,
    ToolCall,
    ToolRegistry,
)


class DummyInput(BaseModel):
    query: str


class DummyOutput(BaseModel):
    result: str


async def dummy_executor(input_data: DummyInput) -> DummyOutput:
    return DummyOutput(result=f"processed: {input_data.query}")


class TestAgentConfiguration:
    def test_agent_settings_defaults(self):
        settings = get_settings()
        assert "prohuman" in settings.database_url
        assert settings.default_llm_model == "gpt-4o"
        assert settings.max_total_hops == 15
        assert settings.token_budget_limit == 200_000


class TestPolicyEngine:
    def test_hop_cap_enforcement(self):
        config = AgentConfig(max_total_hops=5)
        policy = PolicyEngine(config)
        state = AgentState(total_hops=5)
        tools = ToolRegistry()
        tools.register(
            name="test_tool",
            input_schema=DummyInput,
            output_schema=DummyOutput,
            executor=dummy_executor,
        )
        tool_call = ToolCall(call_id="c-1", tool_name="test_tool", arguments={"query": "test"})

        with pytest.raises(PolicyViolation, match="Maximum tool call limit"):
            policy.check(tool_call, state, tools.get("test_tool"))

    def test_token_budget_enforcement(self):
        config = AgentConfig(token_budget_limit=1000)
        policy = PolicyEngine(config)
        state = AgentState(total_tokens_used=1001)
        tools = ToolRegistry()
        tools.register(
            name="test_tool",
            input_schema=DummyInput,
            output_schema=DummyOutput,
            executor=dummy_executor,
        )
        tool_call = ToolCall(call_id="c-2", tool_name="test_tool", arguments={"query": "test"})

        with pytest.raises(PolicyViolation, match="Token budget"):
            policy.check(tool_call, state, tools.get("test_tool"))

    def test_sql_injection_detection(self):
        config = AgentConfig()
        policy = PolicyEngine(config)
        state = AgentState()
        tools = ToolRegistry()
        tools.register(
            name="test_tool",
            input_schema=DummyInput,
            output_schema=DummyOutput,
            executor=dummy_executor,
        )
        malicious_call = ToolCall(
            call_id="c-3",
            tool_name="test_tool",
            arguments={"query": "SELECT * FROM users; DROP TABLE sessions;"},
        )

        with pytest.raises(PolicyViolation, match="Potential injection detected"):
            policy.check(malicious_call, state, tools.get("test_tool"))


class TestToolRegistry:
    def test_register_and_retrieve_tool(self):
        registry = ToolRegistry()
        registry.register(
            name="dummy_tool",
            input_schema=DummyInput,
            output_schema=DummyOutput,
            executor=dummy_executor,
            description="A test tool",
        )
        assert "dummy_tool" in registry.list_names()
        tool_def = registry.get("dummy_tool")
        assert tool_def is not None
        assert tool_def.name == "dummy_tool"
        assert tool_def.description == "A test tool"

    def test_nonexistent_tool(self):
        registry = ToolRegistry()
        assert registry.get("non_existent") is None
