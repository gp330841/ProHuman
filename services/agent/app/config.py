from pydantic_settings import BaseSettings

class AgentSettings(BaseSettings):
    database_url: str
    redis_url: str
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

    model_config = {'env_prefix': 'AGENT_'}

settings = AgentSettings()
