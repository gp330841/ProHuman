from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from app.dependencies import get_transcript_repo
from packages.contracts.search import SearchRequest, SearchResponse
from packages.db.repositories.transcript_repo import TranscriptRepository

router = APIRouter()

@router.post("", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    transcript_repo: TranscriptRepository = Depends(get_transcript_repo)
) -> Any:
    """Hybrid search endpoint."""
    query_embedding = [0.0] * 1536
    if request.search_mode.value != "LEXICAL":
        try:
            import litellm

            resp = await litellm.aembedding(
                model="text-embedding-3-small",
                input=[request.query],
            )
            if not resp.data:
                raise HTTPException(status_code=503, detail="Embedding service returned no vector")
            query_embedding = resp.data[0]["embedding"]
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Embedding service unavailable: {exc}") from exc
    
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
        query_embedding_model=(
            "none" if request.search_mode.value == "LEXICAL" else "text-embedding-3-small"
        ),
        search_mode_used=request.search_mode,
    )

__all__ = ["router"]
