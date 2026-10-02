from __future__ import annotations

import httpx
from fastapi import APIRouter, Request, Response, HTTPException
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter()

AGENT_URL = "http://agent:8001/api/v1/agent"


@router.post("/query")
async def proxy_agent_query(request: Request) -> Response:
    """Forward agent query to agent microservice."""
    try:
        body = await request.body()
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{AGENT_URL}/query",
                content=body,
                headers={"Content-Type": "application/json"},
            )
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                media_type="application/json",
            )
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Agent microservice is unreachable")
    except Exception as e:
        logger.exception("agent_proxy_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
