"""Worker configuration module."""
from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class WorkerSettings(BaseSettings):
    """Configuration settings for the worker service."""
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/prohuman"
    redis_url: str = "redis://localhost:6379/0"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket_name: str = "audio-recordings"
    
    deepgram_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    default_llm_model: str = "gemini-3.8-flash"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    stt_primary_adapter: str = "deepgram"
    stt_fallback_adapter: str | None = None
    max_retries: int = 3

    model_config = SettingsConfigDict(env_prefix="WORKER_", case_sensitive=False, env_file=".env")


@lru_cache()
def get_settings() -> WorkerSettings:
    """Get cached worker settings instance."""
    return WorkerSettings()

settings = get_settings()
