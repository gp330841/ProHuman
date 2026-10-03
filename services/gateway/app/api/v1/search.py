from __future__ import annotations

import os
from typing import Any
import httpx
import structlog
from fastapi import APIRouter, Depends
from app.dependencies import get_transcript_repo
from packages.contracts.search import SearchRequest, SearchResponse
from packages.db.repositories.transcript_repo import TranscriptRepository

logger = structlog.get_logger(__name__)
router = APIRouter()

async def _get_embedding(query: str) -> list[float] | None:
    """Attempt to generate query embedding via Gemini or OpenAI/LiteLLM, returning None on failure."""
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("WORKER_GEMINI_API_KEY")
    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={gemini_key}"
            payload = {
                "model": "models/text-embedding-004",
                "content": {"parts": [{"text": query}]}
            }
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    values = data.get("embedding", {}).get("values", [])
                    if values:
                        # Pad or truncate to 1536 dimensions expected by pgvector schema
                        if len(values) < 1536:
                            values = values + [0.0] * (1536 - len(values))
                        return values[:1536]
        except Exception as e:
            logger.warning("gemini_embedding_failed", error=str(e))

    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        try:
            import litellm
            resp = await litellm.aembedding(
                model="text-embedding-3-small",
                input=[query],
            )
            if resp.data:
                return resp.data[0]["embedding"]
        except Exception as e:
            logger.warning("openai_embedding_failed", error=str(e))

    return None

@router.post("", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    transcript_repo: TranscriptRepository = Depends(get_transcript_repo)
) -> Any:
    """Hybrid search endpoint with graceful fallback."""
    query_embedding = [0.0] * 1536
    used_model = "none"

    if request.search_mode.value != "LEXICAL":
        emb = await _get_embedding(request.query)
        if emb:
            query_embedding = emb
            used_model = "text-embedding-004"
        else:
            logger.info("fallback_to_lexical_fulltext", query=request.query)
    
    results_raw = await transcript_repo.hybrid_search(
        query_text=request.query,
        query_embedding=query_embedding,
        limit=request.limit,
        offset=request.offset,
        session_ids=request.session_ids,
        time_range_start=request.time_range_start,
        time_range_end=request.time_range_end,
        search_mode=request.search_mode.value,
    )
    
    results = [
        {
            "segment_id": r["segment_id"],
            "session_id": r["session_id"],
            "speaker_label": r.get("speaker_label", "speaker_0"),
            "text": r.get("text", ""),
            "start_time": float(r.get("start_time", 0.0)),
            "end_time": float(r.get("end_time", 0.0)),
            "rrf_score": float(r.get("rrf_score", 0.0)),
            "vector_rank": r.get("vector_rank"),
            "text_rank": r.get("text_rank"),
            "session_date": r.get("created_at"),
        }
        for r in results_raw
    ]
    
    return SearchResponse(
        results=results,
        total_count=len(results),
        query_embedding_model=used_model,
        search_mode_used=request.search_mode,
    )

__all__ = ["router"]
