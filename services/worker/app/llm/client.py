from __future__ import annotations

import asyncio
from typing import Any, TypeVar, Type

import litellm
import instructor
from pydantic import BaseModel
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

class LLMClient:
    def __init__(self, default_model: str = "gpt-4o"):
        self.default_model = default_model
        # Configure litellm api keys
        litellm.openai_key = settings.openai_api_key
        
        # Initialize instructor client
        self.instructor_client = instructor.from_litellm(litellm.acompletion)

    async def generate_structured(
        self, 
        messages: list[dict[str, Any]], 
        response_model: Type[T], 
        model: str | None = None, 
        max_retries: int = 3, 
        temperature: float = 0.1
    ) -> T:
        target_model = model or self.default_model
        logger.info("llm_generate_structured", model=target_model, response_model=response_model.__name__)
        
        response = await self.instructor_client.chat.completions.create(
            model=target_model,
            messages=messages,
            response_model=response_model,
            max_retries=max_retries,
            temperature=temperature
        )
        # Note: Instructor automatically handles parsing and retrying against the schema
        
        # We can't directly get usage from instructor response if it returns the pydantic model,
        # but litellm logs could be used, or instructor exposes `_raw_response` in some configurations.
        # For this setup, we just return the model.
        return response

    async def generate_text(
        self, 
        messages: list[dict[str, Any]], 
        model: str | None = None, 
        max_tokens: int = 4096
    ) -> str:
        target_model = model or self.default_model
        logger.info("llm_generate_text", model=target_model)
        
        response = await litellm.acompletion(
            model=target_model,
            messages=messages,
            max_tokens=max_tokens
        )
        
        usage = response.get("usage", {})
        logger.info("llm_usage", prompt_tokens=usage.get("prompt_tokens"), completion_tokens=usage.get("completion_tokens"))
        
        return response.choices[0].message.content

    async def generate_embeddings(
        self, 
        texts: list[str], 
        model: str | None = None
    ) -> list[list[float]]:
        target_model = model or settings.embedding_model
        logger.info("llm_generate_embeddings", model=target_model, text_count=len(texts))
        
        all_embeddings = []
        batch_size = 32
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = await litellm.aembedding(
                model=target_model,
                input=batch
            )
            
            usage = response.get("usage", {})
            logger.info("embedding_usage", prompt_tokens=usage.get("prompt_tokens"))
            
            batch_embeddings = [data["embedding"] for data in response["data"]]
            all_embeddings.extend(batch_embeddings)
            
        return all_embeddings
