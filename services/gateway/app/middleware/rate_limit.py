from __future__ import annotations

import time
from typing import Callable, Awaitable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from redis.asyncio import Redis

from app.dependencies import get_redis

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limit middleware using Redis token bucket."""
    
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Dispatch request through rate limiter."""
        if request.url.path == "/health" or request.url.scheme in ("ws", "wss"):
            return await call_next(request)
            
        client_id = request.headers.get("X-API-Key") or request.client.host if request.client else "unknown"
        minute_bucket = int(time.time() / 60)
        key = f"ratelimit:{client_id}:{minute_bucket}"
        
        # Note: In a real app we'd inject Redis properly, this is simplified for middleware context
        try:
            # Assuming app.state.redis is set up on startup
            redis: Redis = request.app.state.redis
            current = await redis.incr(key)
            if current == 1:
                await redis.expire(key, 60)
                
            if current > 100: # Example limit
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests"},
                    headers={"Retry-After": "60"}
                )
        except AttributeError:
            pass # Redis not set up in state, bypass
            
        return await call_next(request)

__all__ = ["RateLimitMiddleware"]
