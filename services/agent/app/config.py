"""Agent configuration module."""
from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class AgentSettings(BaseSettings):
    """Configuration settings for the agent service."""
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/prohuman"
    redis_url: str = "redis://localhost:6379/0"
    default_llm_model: str = 'gpt-4o'
    embedding_model: str = 'text-embedding-3-small'
    max_total_hops: int = 15
    max_hops_per_subgoal: int = 5
    max_planning_iterations: int = 3
    max_tool_retries: int = 2
    tool_timeout_seconds: float = 30.0
    token_budget_limit: int = 200_000
    otlp_endpoint: str = 'http://localhost:4317'
    webhook_allowlist: list[str] = []
    log_level: str = 'INFO'
    use_ollama: bool = True
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2:3b"
    gemini_api_key: str = ""

    model_config = SettingsConfigDict(env_prefix='AGENT_', env_file=".env", extra="ignore")


@lru_cache()
def get_settings() -> AgentSettings:
    """Get cached agent settings instance."""
    return AgentSettings()

settings = get_settings()
